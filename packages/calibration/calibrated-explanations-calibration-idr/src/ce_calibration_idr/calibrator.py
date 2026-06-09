"""IDR-backed regression interval calibrator implementation."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from ce_calibration_idr.idr_adapter import IDRDistributionAdapter
from ce_calibration_idr.threshold_adapter import IDRThresholdProbabilityAdapter

_LOGGER = logging.getLogger("calibrated_explanations.plugins.idr_regression")


class IDRRegressionIntervalCalibrator:
    """Post-hoc distribution calibrator for scalar regression predictions.

    This object is fitted during CE calibration. It is not the underlying predictive model;
    it maps scalar predictions from the already-fitted learner to a calibrated discrete
    predictive distribution.
    """

    def __init__(
        self,
        *,
        context: Any,
        idr_backend: str = "isodistrreg",
        fast: bool = False,
    ) -> None:
        """Fit the distribution calibrator from a CE interval calibrator context."""
        self._context = context
        self._fast = fast
        self._idr = IDRDistributionAdapter(backend=idr_backend)
        self._learner = self._extract_learner(context)
        self._X_cal, self._y_cal = self._extract_calibration_data(context)
        cal_scores = self._raw_predict(self._X_cal)
        self._idr.fit(cal_scores, self._y_cal)
        self._threshold_adapter = IDRThresholdProbabilityAdapter(
            idr=self._idr,
            learner=self._learner,
            X_cal=self._X_cal,
            y_cal=self._y_cal,
            raw_predict_fn=self._raw_predict,
            venn_abers_factory=self._extract_venn_abers_factory(context),
        )

    def predict_probability(
        self,
        X: Any,
        *,
        threshold: float | tuple[float, float],
        output_interval: bool = True,
        **kwargs: Any,
    ) -> dict[str, np.ndarray]:
        """Return threshold-event probabilities through CE Venn-Abers calibration."""
        return self._predict_threshold_probability(
            X,
            threshold=threshold,
            output_interval=output_interval,
        )

    def predict_proba(
        self,
        X: Any,
        *,
        threshold: float | tuple[float, float],
        output_interval: bool = True,
        **kwargs: Any,
    ) -> dict[str, np.ndarray]:
        """Alias CE probability calls to threshold-event probability prediction."""
        return self.predict_probability(
            X,
            threshold=threshold,
            output_interval=output_interval,
            **kwargs,
        )

    def predict_uncertainty(
        self,
        X: Any,
        *,
        low_high_percentiles: tuple[float, float] = (5.0, 95.0),
        threshold: float | tuple[float, float] | None = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """Return interval width as an uncertainty proxy for CE compatibility."""
        prediction = self.predict(
            X,
            low_high_percentiles=low_high_percentiles,
            threshold=threshold,
            **kwargs,
        )
        return np.asarray(prediction["high"], dtype=float) - np.asarray(
            prediction["low"], dtype=float
        )

    def pre_fit_for_probabilistic(
        self, *args: Any, **kwargs: Any
    ) -> "IDRRegressionIntervalCalibrator":
        """Return self because threshold VA models are fitted lazily per event threshold."""
        return self

    def compute_proba_cal(
        self,
        threshold: float | tuple[float, float],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return calibration event scores and labels for a threshold event."""
        adapter = self._threshold_adapter
        return (
            adapter._event_scores(self._X_cal, threshold),  # noqa: SLF001
            adapter._event_labels(self._y_cal, threshold),  # noqa: SLF001
        )

    def insert_calibration(self, *args: Any, **kwargs: Any) -> None:
        """Reject post-hoc mutation of fitted IDR calibration data."""
        raise NotImplementedError("IDR calibration data are immutable after plugin creation.")

    def is_multiclass(self) -> bool:
        """Return False because this plugin only supports regression events."""
        return False

    def is_mondrian(self) -> bool:
        """Return False because this plugin does not implement Mondrian calibration."""
        return False

    def predict(
        self,
        X: Any,
        *,
        low_high_percentiles: tuple[float, float] = (5.0, 95.0),
        threshold: float | tuple[float, float] | None = None,
        output_interval: bool = True,
        **kwargs: Any,
    ) -> dict[str, np.ndarray]:
        """Return a CE-compatible calibrated prediction payload."""
        if threshold is None:
            return self._predict_regression_interval(
                X,
                low_high_percentiles=low_high_percentiles,
            )
        return self._predict_threshold_probability(
            X,
            threshold=threshold,
            output_interval=output_interval,
        )

    def _predict_regression_interval(
        self,
        X: Any,
        *,
        low_high_percentiles: tuple[float, float],
    ) -> dict[str, np.ndarray]:
        low_pct, high_pct = low_high_percentiles
        low_alpha = self._percentile_to_alpha(low_pct)
        high_alpha = self._percentile_to_alpha(high_pct)
        if low_alpha > 0.5 or high_alpha < 0.5:
            raise ValueError(
                "low_high_percentiles must bracket the calibrated median: low <= 50 <= high."
            )
        scores = self._raw_predict(X)
        low = self._idr.quantile(scores, low_alpha)
        predict = self._idr.quantile(scores, 0.5)
        high = self._idr.quantile(scores, high_alpha)
        low, predict, high = self._repair_ordering(low, predict, high)
        return {
            "predict": predict,
            "low": low,
            "high": high,
            "raw_predict": scores,
            "calibrator": np.asarray(["idr"] * len(predict), dtype=object),
        }

    def _predict_threshold_probability(
        self,
        X: Any,
        *,
        threshold: float | tuple[float, float],
        output_interval: bool,
    ) -> dict[str, np.ndarray]:
        return self._threshold_adapter.predict_probability_interval(
            X,
            threshold=threshold,
            output_interval=output_interval,
        )

    def _raw_predict(self, X: Any) -> np.ndarray:
        pred = self._learner.predict(X)
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
    def _repair_ordering(
        low: np.ndarray,
        predict: np.ndarray,
        high: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Preserve low <= predict <= high without changing calibrated prediction."""
        repaired_low = np.minimum(low, predict)
        repaired_high = np.maximum(high, predict)
        if not (np.array_equal(repaired_low, low) and np.array_equal(repaired_high, high)):
            _LOGGER.info("IDR quantile ordering repair applied to preserve low <= predict <= high.")
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

    @staticmethod
    def _extract_calibration_data(context: Any) -> tuple[Any, np.ndarray]:
        if hasattr(context, "X_cal") and hasattr(context, "y_cal"):
            return context.X_cal, np.asarray(context.y_cal, dtype=float)
        if hasattr(context, "calibration_data"):
            X_cal, y_cal = context.calibration_data
            return X_cal, np.asarray(y_cal, dtype=float)
        if hasattr(context, "X") and hasattr(context, "y"):
            return context.X, np.asarray(context.y, dtype=float)
        raise AttributeError("Could not extract calibration data from IntervalCalibratorContext.")
