"""Split-conformalized IDR regression interval calibrator implementation."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from ce_calibration_idr.idr_adapter import IDRDistributionAdapter
from ce_calibration_idr.threshold_adapter import IDRThresholdProbabilityAdapter

_LOGGER = logging.getLogger("calibrated_explanations.plugins.conformal_idr_regression")


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Return the finite-sample split-conformal quantile for miscoverage level alpha.

    Uses the standard formula k = ceil((n+1)*(1-alpha)) and returns scores_sorted[k-1].
    Raises ``ValueError`` if the calibration set is too small for the requested level.
    """
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1:
        raise ValueError("Conformity scores must be one-dimensional.")
    if not np.all(np.isfinite(scores)):
        raise ValueError("Conformity scores must all be finite.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be strictly between 0 and 1; got {alpha!r}.")
    n = len(scores)
    if n == 0:
        raise ValueError("Cannot compute conformal quantile from an empty score set.")
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        raise ValueError(
            f"Calibration set has {n} held-out examples, but the requested coverage "
            f"level (alpha={alpha:.4f}) requires at least {k} examples "
            f"(k = ceil((n+1)*(1-alpha)) = {k} > n = {n}). "
            "Use a larger calibration set or relax the coverage requirement."
        )
    sorted_scores = np.sort(scores)
    return float(sorted_scores[k - 1])


def _resolve_fit_and_calibration_data(  # noqa: N803
    context: Any,
    idr_X: Any | None,  # noqa: N803
    idr_y: Any | None,
    idr_fraction: float,
    random_state: int | None,
    min_idr_samples: int,
    min_conformal_samples: int,
) -> tuple[Any, np.ndarray, Any, np.ndarray, str]:
    """Resolve IDR-fit data and held-out conformal calibration data.

    Returns (x_idr, y_idr, x_conf, y_conf, data_source) where data_source is
    either 'external_idr_data' or 'split_calibration_data'.
    """
    if (idr_X is None) != (idr_y is None):
        raise ValueError("idr_X and idr_y must both be provided or both omitted.")

    x_cal, y_cal = _extract_calibration_data(context)

    if idr_X is not None:
        return (
            np.asarray(idr_X),
            np.asarray(idr_y, dtype=float),
            x_cal,
            y_cal,
            "external_idr_data",
        )

    # Fallback: split calibration set
    n = len(y_cal)
    n_idr = max(min_idr_samples, int(math.floor(n * idr_fraction)))
    n_conf = n - n_idr
    if n_idr < min_idr_samples:
        raise ValueError(
            f"IDR-fit subset has {n_idr} samples but min_idr_samples={min_idr_samples}. "
            f"Provide a larger calibration set or lower min_idr_samples."
        )
    if n_conf < min_conformal_samples:
        raise ValueError(
            f"Held-out conformal subset has {n_conf} samples but "
            f"min_conformal_samples={min_conformal_samples}. "
            f"Provide a larger calibration set or lower min_conformal_samples."
        )
    rng = np.random.default_rng(random_state)
    indices = rng.permutation(n)
    idr_idx = indices[:n_idr]
    conf_idx = indices[n_idr:]
    x_idr = x_cal[idr_idx]
    y_idr = y_cal[idr_idx]
    x_conf = x_cal[conf_idx]
    y_conf = y_cal[conf_idx]
    return x_idr, y_idr, x_conf, y_conf, "split_calibration_data"


def _extract_calibration_data(context: Any) -> tuple[Any, np.ndarray]:
    """Extract x_cal and y_cal from a CE IntervalCalibratorContext."""
    if hasattr(context, "X_cal") and hasattr(context, "y_cal"):
        return context.X_cal, np.asarray(context.y_cal, dtype=float)
    if hasattr(context, "calibration_splits"):
        calibration_splits = context.calibration_splits
        if calibration_splits:
            x_cal, y_cal = calibration_splits[0]
            return x_cal, np.asarray(y_cal, dtype=float)
    if hasattr(context, "calibration_data"):
        x_cal, y_cal = context.calibration_data
        return x_cal, np.asarray(y_cal, dtype=float)
    if hasattr(context, "X") and hasattr(context, "y"):
        return context.X, np.asarray(context.y, dtype=float)
    raise AttributeError("Could not extract calibration data from IntervalCalibratorContext.")


class ConformalIDRRegressionIntervalCalibrator:
    """Split-conformalized IDR regression interval calibrator.

    Fits IDR on a separate IDR-fit dataset and applies a split-conformal correction
    computed on held-out calibration data not used to fit IDR. This provides a
    finite-sample marginal coverage guarantee under exchangeability of the held-out
    calibration examples and future test examples.

    The guarantee is marginal coverage only. Conditional coverage is not claimed.
    Conformal validity holds only when calibration/test exchangeability holds.

    For ordinary regression intervals, the conformal correction is computed from
    held-out calibration data. For threshold mode, the IDR distribution is used
    to compute event scores and Venn-Abers calibration is applied using the
    held-out calibration subset.
    """

    def __init__(  # noqa: N803
        self,
        *,
        context: Any,
        idr_X: Any | None = None,  # noqa: N803
        idr_y: Any | None = None,
        idr_backend: str = "isodistrreg",
        idr_fraction: float = 0.5,
        random_state: int | None = None,
        min_idr_samples: int = 2,
        min_conformal_samples: int = 20,
    ) -> None:
        """Fit the conformal IDR calibrator from a CE interval calibrator context."""
        self._context = context
        self._idr = IDRDistributionAdapter(backend=idr_backend)
        self._learner = self._extract_learner(context)
        self._qhat_cache: dict[tuple[float, float], float] = {}

        x_idr, y_idr, x_conf, y_conf, data_source = _resolve_fit_and_calibration_data(
            context=context,
            idr_X=idr_X,
            idr_y=idr_y,
            idr_fraction=idr_fraction,
            random_state=random_state,
            min_idr_samples=min_idr_samples,
            min_conformal_samples=min_conformal_samples,
        )

        self._data_source = data_source
        self._n_idr = len(y_idr)
        self._n_conformal = len(y_conf)
        self._X_conf = x_conf
        self._y_conf = y_conf

        # Fit IDR on the IDR-fit subset only
        idr_scores = self._raw_predict(x_idr)
        self._idr.fit(idr_scores, y_idr)

        # Compute held-out raw scores for conformal/threshold calibration
        self._conf_scores = self._raw_predict(x_conf)

        self._threshold_adapter = IDRThresholdProbabilityAdapter(
            idr=self._idr,
            learner=self._learner,
            x_cal=x_conf,
            y_cal=y_conf,
            raw_predict_fn=self._raw_predict,
            venn_abers_factory=self._extract_venn_abers_factory(context),
        )

    # ------------------------------------------------------------------
    # CE-compatible public surface
    # ------------------------------------------------------------------

    def predict_probability(
        self,
        x: Any,
        threshold: float | tuple[float, float],
        *,
        output_interval: bool = True,
        **kwargs: Any,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Return threshold-event probabilities through CE Venn-Abers calibration."""
        prediction = self._predict_threshold_probability(
            x,
            threshold=threshold,
            output_interval=output_interval,
        )
        return prediction["predict"], prediction["low"], prediction["high"], None

    def predict_proba(
        self,
        x: Any,
        threshold: float | tuple[float, float],
        *,
        output_interval: bool = True,
        **kwargs: Any,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Alias CE probability calls to threshold-event probability prediction."""
        return self.predict_probability(
            x,
            threshold=threshold,
            output_interval=output_interval,
            **kwargs,
        )

    def predict_uncertainty(
        self,
        x: Any,
        low_high_percentiles: tuple[float, float] = (5.0, 95.0),
        bins: Any | None = None,
        *,
        threshold: float | tuple[float, float] | None = None,
        **kwargs: Any,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Return CE-compatible regression prediction interval components."""
        prediction = self.predict(
            x,
            low_high_percentiles=low_high_percentiles,
            threshold=threshold,
            **kwargs,
        )
        return prediction["predict"], prediction["low"], prediction["high"], None

    def pre_fit_for_probabilistic(
        self, *args: Any, **kwargs: Any
    ) -> "ConformalIDRRegressionIntervalCalibrator":
        """Return self because threshold VA models are fitted lazily per event threshold."""
        return self

    def compute_proba_cal(
        self,
        threshold: float | tuple[float, float],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return calibration event scores and labels for a threshold event."""
        adapter = self._threshold_adapter
        return (
            adapter._event_scores(self._X_conf, threshold),  # noqa: SLF001
            adapter._event_labels(self._y_conf, threshold),  # noqa: SLF001
        )

    def insert_calibration(self, *args: Any, **kwargs: Any) -> None:
        """Reject post-hoc mutation of fitted conformal IDR calibration state.

        Conformal IDR update support requires a valid refit/recalibration protocol
        that preserves the IDR/conformal data separation invariant. This is not
        implemented and will be considered in a future version.
        """
        raise NotImplementedError(
            "ConformalIDRRegressionIntervalCalibrator does not support insert_calibration. "
            "Conformal IDR update support requires a valid refit/recalibration protocol "
            "that preserves the IDR/conformal data separation invariant."
        )

    def is_multiclass(self) -> bool:
        """Return False because this plugin only supports regression events."""
        return False

    def is_mondrian(self) -> bool:
        """Return False because this plugin does not implement Mondrian calibration."""
        return False

    def predict(
        self,
        x: Any,
        *,
        low_high_percentiles: tuple[float, float] = (5.0, 95.0),
        threshold: float | tuple[float, float] | None = None,
        output_interval: bool = True,
        **kwargs: Any,
    ) -> dict[str, np.ndarray]:
        """Return a CE-compatible calibrated prediction payload."""
        if threshold is None:
            return self._predict_regression_interval(
                x,
                low_high_percentiles=low_high_percentiles,
            )
        return self._predict_threshold_probability(
            x,
            threshold=threshold,
            output_interval=output_interval,
        )

    # ------------------------------------------------------------------
    # Regression interval logic
    # ------------------------------------------------------------------

    def _predict_regression_interval(
        self,
        x: Any,
        *,
        low_high_percentiles: tuple[float, float],
    ) -> dict[str, np.ndarray]:
        low_pct, high_pct = low_high_percentiles
        self._validate_percentiles(low_pct, high_pct)

        low_alpha = self._percentile_to_alpha(low_pct)
        high_alpha = self._percentile_to_alpha(high_pct)

        low_finite = low_pct != -np.inf
        high_finite = high_pct != np.inf

        raw_scores = self._raw_predict(x)
        n_test = len(raw_scores)

        # Base IDR median for test points
        m_test = self._idr.quantile(raw_scores, 0.5)

        if low_finite and high_finite:
            # Two-sided interval
            alpha = low_alpha + (1.0 - high_alpha)
            qhat = self._get_or_compute_qhat(low_pct, high_pct, alpha, mode="two_sided")
            q_low_test = self._idr.quantile(raw_scores, low_alpha)
            q_high_test = self._idr.quantile(raw_scores, high_alpha)
            low = q_low_test - qhat
            predict = m_test
            high = q_high_test + qhat

        elif not low_finite and high_finite:
            # One-sided upper interval (-inf, high_pct)
            alpha = 1.0 - high_alpha
            qhat = self._get_or_compute_qhat(low_pct, high_pct, alpha, mode="upper")
            q_high_test = self._idr.quantile(raw_scores, high_alpha)
            low = np.full(n_test, float(np.min(self._y_conf)))
            predict = m_test
            high = q_high_test + qhat

        else:
            # One-sided lower interval (low_pct, +inf)
            alpha = low_alpha
            qhat = self._get_or_compute_qhat(low_pct, high_pct, alpha, mode="lower")
            q_low_test = self._idr.quantile(raw_scores, low_alpha)
            low = q_low_test - qhat
            predict = m_test
            high = np.full(n_test, float(np.max(self._y_conf)))

        low, predict, high = self._repair_ordering(low, predict, high)

        return {
            "predict": predict,
            "low": low,
            "high": high,
            "raw_predict": raw_scores,
            "calibrator": np.asarray(["conformal_idr"] * n_test, dtype=object),
            "conformal_qhat": np.full(n_test, qhat),
            "conformal_alpha": np.full(n_test, alpha),
        }

    def _get_or_compute_qhat(
        self,
        low_pct: float,
        high_pct: float,
        alpha: float,
        mode: str,
    ) -> float:
        """Return cached or freshly computed conformal quantile correction."""
        cache_key = (low_pct, high_pct)
        if cache_key in self._qhat_cache:
            return self._qhat_cache[cache_key]

        low_alpha = self._percentile_to_alpha(low_pct)
        high_alpha = self._percentile_to_alpha(high_pct)

        if mode == "two_sided":
            q_low_cal = self._idr.quantile(self._conf_scores, low_alpha)
            q_high_cal = self._idr.quantile(self._conf_scores, high_alpha)
            scores = np.maximum.reduce(
                [q_low_cal - self._y_conf, self._y_conf - q_high_cal, np.zeros_like(self._y_conf)]
            )

        elif mode == "upper":
            q_high_cal = self._idr.quantile(self._conf_scores, high_alpha)
            scores = np.maximum(self._y_conf - q_high_cal, 0.0)

        else:  # lower
            q_low_cal = self._idr.quantile(self._conf_scores, low_alpha)
            scores = np.maximum(q_low_cal - self._y_conf, 0.0)

        qhat = _conformal_quantile(scores, alpha)
        self._qhat_cache[cache_key] = qhat
        return qhat

    # ------------------------------------------------------------------
    # Threshold mode
    # ------------------------------------------------------------------

    def _predict_threshold_probability(
        self,
        x: Any,
        *,
        threshold: float | tuple[float, float],
        output_interval: bool,
    ) -> dict[str, np.ndarray]:
        return self._threshold_adapter.predict_probability_interval(
            x,
            threshold=threshold,
            output_interval=output_interval,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _raw_predict(self, x: Any) -> np.ndarray:
        pred = self._learner.predict(x)
        pred = np.asarray(pred, dtype=float)
        if pred.ndim == 2 and pred.shape[1] == 1:
            pred = pred[:, 0]
        if pred.ndim != 1:
            raise ValueError("Regression learner predictions must be one-dimensional.")
        return pred

    @staticmethod
    def _percentile_to_alpha(percentile: float) -> float:
        if percentile == -np.inf:
            return 0.0
        if percentile == np.inf:
            return 1.0
        if not 0.0 <= percentile <= 100.0:
            raise ValueError("Percentiles must be in [0, 100] or +/- np.inf.")
        return percentile / 100.0

    @staticmethod
    def _validate_percentiles(low_pct: float, high_pct: float) -> None:
        """Raise ValueError for invalid percentile combinations."""
        low_finite = low_pct != -np.inf
        high_finite = high_pct != np.inf

        if not low_finite and not high_finite:
            raise ValueError(
                "Both low and high percentile bounds are infinite. "
                "Provide at least one finite bound."
            )
        if low_finite and not (0.0 <= low_pct <= 100.0):
            raise ValueError(f"low percentile must be in [0, 100]; got {low_pct!r}.")
        if high_finite and not (0.0 <= high_pct <= 100.0):
            raise ValueError(f"high percentile must be in [0, 100]; got {high_pct!r}.")
        if low_finite and high_finite:
            if low_pct > high_pct:
                raise ValueError(
                    f"low_pct ({low_pct}) must be <= high_pct ({high_pct})."
                )
            low_alpha = low_pct / 100.0
            high_alpha = high_pct / 100.0
            if low_alpha > 0.5 or high_alpha < 0.5:
                raise ValueError(
                    "low_high_percentiles must bracket the calibrated median: "
                    "low <= 50 <= high."
                )

    @staticmethod
    def _repair_ordering(
        low: np.ndarray,
        predict: np.ndarray,
        high: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Repair only numerical ordering violations; do not hide logical errors."""
        repaired_low = np.minimum(low, predict)
        repaired_high = np.maximum(high, predict)
        if not (np.array_equal(repaired_low, low) and np.array_equal(repaired_high, high)):
            _LOGGER.info(
                "Conformal IDR quantile ordering repair applied to preserve low <= predict <= high."
            )
        return repaired_low, predict, repaired_high

    @staticmethod
    def _extract_venn_abers_factory(context: Any) -> Any:
        for attr in ("venn_abers_factory", "create_probability_interval_calibrator"):
            factory = getattr(context, attr, None)
            if callable(factory):
                return factory
        return None

    @staticmethod
    def _extract_learner(context: Any) -> Any:
        for attr in ("learner", "model", "estimator"):
            if hasattr(context, attr):
                return getattr(context, attr)
        raise AttributeError("IntervalCalibratorContext does not expose learner.")
