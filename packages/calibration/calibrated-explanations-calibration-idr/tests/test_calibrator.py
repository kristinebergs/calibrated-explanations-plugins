"""Unit tests for the IDR regression interval calibrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

np = pytest.importorskip("numpy")
from ce_calibration_idr.calibrator import IDRRegressionIntervalCalibrator  # noqa: E402


class FakeIDR:
    """Small fake with the subset of isodistrreg.IDR used by the adapter."""

    def __init__(self, *, X: np.ndarray, y: np.ndarray) -> None:
        """Store calibration pairs for deterministic fake distributions."""
        self.X = np.asarray(X, dtype=float).reshape(-1)
        self.y = np.asarray(y, dtype=float)
        self.y_min = float(np.min(self.y))
        self.y_max = float(np.max(self.y))

    def cdf_at(self, X: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
        """Return fake CDF values clipped to probability space."""
        x = np.asarray(X, dtype=float).reshape(-1)
        t = np.asarray(thresholds, dtype=float).reshape(-1)
        return 1.0 / (1.0 + np.exp(-(t - x)))

    def quantile(self, X: np.ndarray, probabilities: float) -> np.ndarray:
        """Return fake quantiles that differ from raw scores."""
        x = np.asarray(X, dtype=float).reshape(-1)
        return np.clip(x + float(probabilities) + 1.0, self.y_min, self.y_max)


class LinearLearner:
    """Tiny deterministic learner for calibrator tests."""

    def predict(self, X: Any) -> np.ndarray:
        """Return the first column as a scalar regression score."""
        return np.asarray(X, dtype=float)[:, 0]


class FakeVennAbers:
    """Fake VA object that visibly changes event scores."""

    def __init__(self, scores: np.ndarray, labels: np.ndarray) -> None:
        """Store fitted calibration data."""
        self.scores = np.asarray(scores, dtype=float)
        self.labels = np.asarray(labels, dtype=int)

    def predict_proba(self, scores: np.ndarray, *, output_interval: bool) -> dict[str, np.ndarray]:
        """Return shifted probability intervals to prove delegation is used."""
        base = np.clip(np.asarray(scores, dtype=float).reshape(-1) * 0.8 + 0.1, 0.0, 1.0)
        return {
            "predict": base,
            "low": np.maximum(0.0, base - 0.1),
            "high": np.minimum(1.0, base + 0.1),
        }


@dataclass
class Context:
    """Minimal CE-like interval calibrator context."""

    learner: LinearLearner
    X_cal: np.ndarray
    y_cal: np.ndarray
    mode: str = "regression"

    def venn_abers_factory(self, scores: np.ndarray, labels: np.ndarray) -> FakeVennAbers:
        """Return a fake CE Venn-Abers probability calibrator."""
        return FakeVennAbers(scores, labels)


def fitted_calibrator(monkeypatch: pytest.MonkeyPatch) -> IDRRegressionIntervalCalibrator:
    """Return a deterministic fitted IDR calibrator."""
    from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402

    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    X_cal = np.arange(8, dtype=float).reshape(-1, 1)
    y_cal = np.array([2.0, 2.0, 4.0, 5.0, 7.0, 7.0, 9.0, 10.0])
    return IDRRegressionIntervalCalibrator(
        context=Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    )


def test_should_return_ordered_regression_interval(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    pred = calibrator.predict(np.array([[1.5], [5.5]]), low_high_percentiles=(5, 95))
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])


def test_should_use_idr_median_as_predict_not_raw_prediction(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    pred = calibrator.predict(np.array([[1.5], [5.5]]))
    assert not np.allclose(pred["predict"], pred["raw_predict"])


def test_should_reject_percentiles_that_do_not_bracket_median(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    with pytest.raises(ValueError, match="bracket"):
        calibrator.predict(np.array([[1.0]]), low_high_percentiles=(60, 90))


def test_should_support_one_sided_percentile_bounds(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    upper = calibrator.predict(np.array([[1.0], [4.0]]), low_high_percentiles=(-np.inf, 90))
    assert np.all(upper["low"] <= upper["predict"])
    assert np.all(upper["predict"] <= upper["high"])


def test_should_return_probability_interval_for_scalar_threshold(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    pred = calibrator.predict(np.array([[1.0], [4.0]]), threshold=5.0, output_interval=True)
    assert np.all(0.0 <= pred["low"])
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])
    assert np.all(pred["high"] <= 1.0)


def test_should_return_probability_interval_for_within_spec_threshold(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    pred = calibrator.predict(np.array([[1.0], [4.0]]), threshold=(4.0, 8.0))
    assert np.all(0.0 <= pred["low"])
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])
    assert np.all(pred["high"] <= 1.0)


def test_should_reject_reversed_within_spec_threshold(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    with pytest.raises(ValueError, match="lower must be <= upper"):
        calibrator.predict(np.array([[1.0]]), threshold=(8.0, 4.0))


def test_threshold_mode_should_delegate_to_venn_abers(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    calls = {"count": 0}
    original = calibrator._threshold_adapter._predict_with_venn_abers  # noqa: SLF001

    def spy(*args: Any, **kwargs: Any):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(calibrator._threshold_adapter, "_predict_with_venn_abers", spy)  # noqa: SLF001
    calibrator.predict(np.array([[1.0]]), threshold=5.0)
    assert calls["count"] == 1


def test_threshold_mode_predict_should_not_equal_raw_idr_score_when_va_changes_it(monkeypatch):
    calibrator = fitted_calibrator(monkeypatch)
    pred = calibrator.predict(np.array([[1.0], [4.0]]), threshold=5.0)
    assert not np.allclose(pred["predict"], pred["event_score"])


def test_plugin_create_rejects_non_regression_context(monkeypatch):
    from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402
    from ce_calibration_idr.plugin import IDRRegressionIntervalCalibratorPlugin  # noqa: E402

    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    context = Context(
        learner=LinearLearner(),
        X_cal=np.arange(8, dtype=float).reshape(-1, 1),
        y_cal=np.arange(8, dtype=float),
        mode="classification",
    )
    with pytest.raises(TypeError, match="only supports regression"):
        IDRRegressionIntervalCalibratorPlugin().create(context)


def test_created_calibrator_exposes_ce_regression_interval_surface(monkeypatch):
    from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402
    from ce_calibration_idr.plugin import IDRRegressionIntervalCalibratorPlugin  # noqa: E402

    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    context = Context(
        learner=LinearLearner(),
        X_cal=np.arange(8, dtype=float).reshape(-1, 1),
        y_cal=np.arange(8, dtype=float),
    )
    calibrator = IDRRegressionIntervalCalibratorPlugin().create(context)
    for method_name in (
        "predict",
        "predict_probability",
        "predict_proba",
        "predict_uncertainty",
        "pre_fit_for_probabilistic",
        "compute_proba_cal",
        "insert_calibration",
        "is_multiclass",
        "is_mondrian",
    ):
        assert callable(getattr(calibrator, method_name))


@dataclass
class ContextWithoutVennAbersFactory:
    """Regression context that intentionally omits a probability interval factory."""

    learner: LinearLearner
    X_cal: np.ndarray
    y_cal: np.ndarray
    mode: str = "regression"


def test_threshold_mode_fails_without_probability_interval_factory(monkeypatch):
    from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402

    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    calibrator = IDRRegressionIntervalCalibrator(
        context=ContextWithoutVennAbersFactory(
            learner=LinearLearner(),
            X_cal=np.arange(8, dtype=float).reshape(-1, 1),
            y_cal=np.arange(8, dtype=float),
        )
    )
    with pytest.raises(RuntimeError, match="Venn-Abers factory"):
        calibrator.predict(np.array([[1.0], [2.0]]), threshold=3.0)
