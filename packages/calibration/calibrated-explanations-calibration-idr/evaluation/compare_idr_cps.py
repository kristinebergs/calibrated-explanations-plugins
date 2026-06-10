"""Compare IDR and default CPS regression interval parity and speed.

This evaluation intentionally uses the same fitted regression model state for
both calibrators. The only changed variable is the interval calibrator selected
by CE.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from sklearn.datasets import make_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from calibrated_explanations import WrapCalibratedExplainer  # noqa: E402
from ce_calibration_idr import IDRRegressionIntervalCalibratorPlugin  # noqa: E402

LEGACY_CPS_ID = "core.interval.legacy"
IDR_ID = IDRRegressionIntervalCalibratorPlugin.plugin_meta["name"]


@dataclass(frozen=True)
class EvaluationData:
    """Deterministic train/calibration/evaluation split."""

    X_train: np.ndarray
    y_train: np.ndarray
    X_cal: np.ndarray
    y_cal: np.ndarray
    X_eval: np.ndarray
    y_eval: np.ndarray


@dataclass(frozen=True)
class PredictionResult:
    """Prediction interval arrays and elapsed prediction time."""

    predict: np.ndarray
    low: np.ndarray
    high: np.ndarray
    elapsed_seconds: float


@dataclass(frozen=True)
class CalibratorRun:
    """Calibrated wrapper, prediction payload, and calibration timing."""

    wrapper: WrapCalibratedExplainer
    prediction: PredictionResult
    calibration_seconds: float


def make_data(*, random_state: int, n_samples: int, n_features: int) -> EvaluationData:
    """Create a deterministic regression split for the comparison."""
    x_all, y = make_regression(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=max(2, n_features - 2),
        noise=8.0,
        random_state=random_state,
    )
    x_train, x_holdout, y_train, y_holdout = train_test_split(
        x_all,
        y,
        test_size=0.4,
        random_state=random_state,
    )
    x_cal, x_eval, y_cal, y_eval = train_test_split(
        x_holdout,
        y_holdout,
        test_size=0.5,
        random_state=random_state,
    )
    return EvaluationData(
        X_train=x_train,
        y_train=y_train,
        X_cal=x_cal,
        y_cal=y_cal,
        X_eval=x_eval,
        y_eval=y_eval,
    )


def fit_underlying_model(
    data: EvaluationData,
    *,
    random_state: int,
    n_estimators: int,
) -> RandomForestRegressor:
    """Fit the single underlying model state used by both calibrators."""
    return RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=1,
    ).fit(data.X_train, data.y_train)


def run_calibrator(
    *,
    model: RandomForestRegressor,
    data: EvaluationData,
    interval_plugin: str | IDRRegressionIntervalCalibratorPlugin,
    low_high_percentiles: tuple[float, float],
) -> CalibratorRun:
    """Calibrate and predict through CE using one interval calibrator."""
    wrapper = WrapCalibratedExplainer(copy.deepcopy(model))
    start = perf_counter()
    wrapper.calibrate(
        data.X_cal,
        data.y_cal,
        mode="regression",
        interval_plugin=interval_plugin,
    )
    calibration_seconds = perf_counter() - start

    start = perf_counter()
    predict, interval = wrapper.predict(
        data.X_eval,
        uq_interval=True,
        low_high_percentiles=low_high_percentiles,
    )
    prediction_seconds = perf_counter() - start
    low, high = interval
    return CalibratorRun(
        wrapper=wrapper,
        prediction=PredictionResult(
            predict=np.asarray(predict, dtype=float),
            low=np.asarray(low, dtype=float),
            high=np.asarray(high, dtype=float),
            elapsed_seconds=prediction_seconds,
        ),
        calibration_seconds=calibration_seconds,
    )


def summarize_prediction(result: PredictionResult, y_true: np.ndarray) -> dict[str, float]:
    """Summarize interval validity and empirical performance for one calibrator."""
    width = result.high - result.low
    covered = (result.low <= y_true) & (y_true <= result.high)
    valid = result.low <= result.high
    contains_predict = (result.low <= result.predict) & (result.predict <= result.high)
    return {
        "coverage": float(np.mean(covered)),
        "mean_interval_width": float(np.mean(width)),
        "median_interval_width": float(np.median(width)),
        "valid_interval_rate": float(np.mean(valid)),
        "contains_predict_rate": float(np.mean(contains_predict)),
        "mean_prediction": float(np.mean(result.predict)),
    }


def compare_predictions(
    *,
    legacy: PredictionResult,
    idr: PredictionResult,
    y_true: np.ndarray,
    raw_legacy: np.ndarray,
    raw_idr: np.ndarray,
) -> dict[str, float | bool]:
    """Compare IDR outputs against the default CPS outputs."""
    legacy_summary = summarize_prediction(legacy, y_true)
    idr_summary = summarize_prediction(idr, y_true)
    return {
        "same_underlying_model": bool(np.allclose(raw_legacy, raw_idr, rtol=0.0, atol=1e-12)),
        "max_raw_prediction_delta": float(np.max(np.abs(raw_legacy - raw_idr))),
        "mean_abs_predict_delta": float(np.mean(np.abs(idr.predict - legacy.predict))),
        "mean_abs_low_delta": float(np.mean(np.abs(idr.low - legacy.low))),
        "mean_abs_high_delta": float(np.mean(np.abs(idr.high - legacy.high))),
        "coverage_delta": float(idr_summary["coverage"] - legacy_summary["coverage"]),
        "mean_width_delta": float(
            idr_summary["mean_interval_width"] - legacy_summary["mean_interval_width"]
        ),
        "median_width_delta": float(
            idr_summary["median_interval_width"] - legacy_summary["median_interval_width"]
        ),
    }


def median_timing(
    *,
    model: RandomForestRegressor,
    data: EvaluationData,
    interval_plugin: str | IDRRegressionIntervalCalibratorPlugin,
    low_high_percentiles: tuple[float, float],
    repeats: int,
) -> tuple[float, float]:
    """Return median calibration and prediction timings for a calibrator."""
    calibration_times: list[float] = []
    prediction_times: list[float] = []
    for _ in range(repeats):
        run = run_calibrator(
            model=model,
            data=data,
            interval_plugin=interval_plugin,
            low_high_percentiles=low_high_percentiles,
        )
        calibration_times.append(run.calibration_seconds)
        prediction_times.append(run.prediction.elapsed_seconds)
    return statistics.median(calibration_times), statistics.median(prediction_times)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    """Build the complete parity and speed report."""
    low_high_percentiles = (float(args.low_percentile), float(args.high_percentile))
    data = make_data(
        random_state=args.random_state,
        n_samples=args.samples,
        n_features=args.features,
    )
    model = fit_underlying_model(
        data,
        random_state=args.random_state,
        n_estimators=args.estimators,
    )

    legacy_run = run_calibrator(
        model=model,
        data=data,
        interval_plugin=LEGACY_CPS_ID,
        low_high_percentiles=low_high_percentiles,
    )
    idr_run = run_calibrator(
        model=model,
        data=data,
        interval_plugin=IDRRegressionIntervalCalibratorPlugin(),
        low_high_percentiles=low_high_percentiles,
    )
    raw_legacy = legacy_run.wrapper.learner.predict(data.X_eval)
    raw_idr = idr_run.wrapper.learner.predict(data.X_eval)

    legacy_calibration, legacy_prediction = median_timing(
        model=model,
        data=data,
        interval_plugin=LEGACY_CPS_ID,
        low_high_percentiles=low_high_percentiles,
        repeats=args.repeats,
    )
    idr_calibration, idr_prediction = median_timing(
        model=model,
        data=data,
        interval_plugin=IDRRegressionIntervalCalibratorPlugin(),
        low_high_percentiles=low_high_percentiles,
        repeats=args.repeats,
    )

    speed = {
        "legacy_cps_calibration_seconds": legacy_calibration,
        "idr_calibration_seconds": idr_calibration,
        "idr_to_legacy_calibration_ratio": idr_calibration / legacy_calibration,
        "legacy_cps_prediction_seconds": legacy_prediction,
        "idr_prediction_seconds": idr_prediction,
        "idr_to_legacy_prediction_ratio": idr_prediction / legacy_prediction,
    }
    return {
        "configuration": {
            "samples": args.samples,
            "features": args.features,
            "estimators": args.estimators,
            "repeats": args.repeats,
            "random_state": args.random_state,
            "low_high_percentiles": low_high_percentiles,
            "legacy_cps_plugin": LEGACY_CPS_ID,
            "idr_plugin": IDR_ID,
        },
        "legacy_cps": summarize_prediction(legacy_run.prediction, data.y_eval),
        "idr": summarize_prediction(idr_run.prediction, data.y_eval),
        "parity": compare_predictions(
            legacy=legacy_run.prediction,
            idr=idr_run.prediction,
            y_true=data.y_eval,
            raw_legacy=raw_legacy,
            raw_idr=raw_idr,
        ),
        "speed": speed,
    }


def print_report(report: dict[str, Any]) -> None:
    """Print a compact human-readable report."""
    print("IDR vs default CPS regression interval evaluation")
    print(json.dumps(report["configuration"], indent=2, sort_keys=True))
    for section in ("legacy_cps", "idr", "parity", "speed"):
        print(f"\n{section}:")
        for key, value in report[section].items():
            if isinstance(value, float):
                print(f"  {key}: {value:.6g}")
            else:
                print(f"  {key}: {value}")


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=400)
    parser.add_argument("--features", type=int, default=8)
    parser.add_argument("--estimators", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=0)
    parser.add_argument("--low-percentile", type=float, default=5.0)
    parser.add_argument("--high-percentile", type=float, default=95.0)
    parser.add_argument("--json", type=Path, default=None, help="Optional path for JSON output.")
    return parser.parse_args()


def main() -> None:
    """Run the evaluation script."""
    args = parse_args()
    report = build_report(args)
    print_report(report)
    if args.json is not None:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
