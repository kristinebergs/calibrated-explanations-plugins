"""Threshold probability adapter for distribution event scores and Venn-Abers intervals."""

from __future__ import annotations

from typing import Any, Callable, Protocol

import numpy as np


class VennAbersFactory(Protocol):
    """Stable CE-supplied factory protocol used by threshold probability calibration."""

    def __call__(self, scores: np.ndarray, labels: np.ndarray) -> Any:
        """Fit and return a CE Venn-Abers probability interval calibrator."""


class IDRThresholdProbabilityAdapter:
    """Convert calibrated distributions into event scores and delegate intervals to VA."""

    def __init__(
        self,
        *,
        idr: Any,
        learner: Any,
        x_cal: Any,
        y_cal: np.ndarray,
        raw_predict_fn: Callable[[Any], np.ndarray],
        venn_abers_factory: VennAbersFactory | None,
    ) -> None:
        """Create a threshold adapter for a fitted distribution calibrator."""
        self._idr = idr
        self._learner = learner
        self._X_cal = x_cal
        self._y_cal = np.asarray(y_cal, dtype=float)
        self._raw_predict = raw_predict_fn
        self._venn_abers_factory = venn_abers_factory
        self._va_cache: dict[tuple[str, float, float | None], Any] = {}

    def predict_probability_interval(
        self,
        x: Any,
        *,
        threshold: float | tuple[float, float],
        output_interval: bool,
    ) -> dict[str, np.ndarray]:
        """Return Venn-Abers calibrated event probability predictions and intervals."""
        event_key = self._event_key(threshold)
        va = self._get_or_fit_venn_abers(threshold, event_key)
        scores_query = self._event_scores(x, threshold)
        predict, low, high = self._predict_with_venn_abers(
            va,
            scores_query,
            output_interval=output_interval,
        )
        low, predict, high = self._clip_and_repair_probability_interval(low, predict, high)
        return {
            "predict": predict,
            "low": low,
            "high": high,
            "event_score": scores_query,
            "calibrator": np.asarray(["idr+venn_abers"] * len(predict), dtype=object),
        }

    def _get_or_fit_venn_abers(
        self,
        threshold: float | tuple[float, float],
        event_key: tuple[str, float, float | None],
    ) -> Any:
        if event_key in self._va_cache:
            return self._va_cache[event_key]
        scores_cal = self._event_scores(self._X_cal, threshold)
        labels_cal = self._event_labels(self._y_cal, threshold)
        va = self._fit_venn_abers(scores_cal, labels_cal)
        self._va_cache[event_key] = va
        return va

    def _event_scores(self, x: Any, threshold: float | tuple[float, float]) -> np.ndarray:
        raw_scores = self._raw_predict(x)
        if isinstance(threshold, tuple):
            lower, upper = threshold
            if lower > upper:
                raise ValueError("For threshold=(lower, upper), lower must be <= upper.")
            p_upper = self._idr.cdf(raw_scores, upper)
            lower_left_limit = np.nextafter(float(lower), -np.inf)
            p_below_lower = self._idr.cdf(raw_scores, lower_left_limit)
            return np.clip(p_upper - p_below_lower, 0.0, 1.0)
        return np.clip(self._idr.cdf(raw_scores, float(threshold)), 0.0, 1.0)

    @staticmethod
    def _event_labels(y: np.ndarray, threshold: float | tuple[float, float]) -> np.ndarray:
        """Return binary calibration labels for the configured threshold event."""
        y = np.asarray(y, dtype=float)
        if isinstance(threshold, tuple):
            lower, upper = threshold
            if lower > upper:
                raise ValueError("For threshold=(lower, upper), lower must be <= upper.")
            return ((lower <= y) & (y <= upper)).astype(int)
        return (y <= float(threshold)).astype(int)

    @staticmethod
    def _event_key(threshold: float | tuple[float, float]) -> tuple[str, float, float | None]:
        """Return a cache key for a scalar or within-spec threshold."""
        if isinstance(threshold, tuple):
            lower, upper = threshold
            return ("within", float(lower), float(upper))
        return ("leq", float(threshold), None)

    def _fit_venn_abers(self, scores: np.ndarray, labels: np.ndarray) -> Any:
        """Fit CE's Venn-Abers implementation through a stable context-provided factory."""
        if self._venn_abers_factory is None:
            raise RuntimeError(
                "Threshold probability calibration requires the CE context to provide a "
                "Venn-Abers factory, for example context.venn_abers_factory or "
                "context.create_probability_interval_calibrator. The IDR plugin does not "
                "dynamically import CE internals or implement its own probability interval method."
            )
        return self._venn_abers_factory(scores.reshape(-1, 1), labels)

    def _predict_with_venn_abers(
        self,
        va: Any,
        scores: np.ndarray,
        *,
        output_interval: bool,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return final calibrated probability, lower bound, and upper bound from VA."""
        query = np.asarray(scores, dtype=float).reshape(-1, 1)
        if not hasattr(va, "predict_proba"):
            raise TypeError("CE Venn-Abers calibrator must expose predict_proba(...).")
        result = va.predict_proba(query, output_interval=output_interval)
        return self._normalise_venn_abers_output(result)

    @staticmethod
    def _normalise_venn_abers_output(result: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Normalize the stable CE Venn-Abers output contract."""
        if not isinstance(result, dict):
            raise TypeError("CE Venn-Abers output must be a mapping with predict, low, and high.")
        return (
            np.asarray(result["predict"], dtype=float),
            np.asarray(result["low"], dtype=float),
            np.asarray(result["high"], dtype=float),
        )

    @staticmethod
    def _clip_and_repair_probability_interval(
        low: np.ndarray,
        predict: np.ndarray,
        high: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Clip and repair probability outputs to preserve VA interval invariants."""
        low = np.clip(np.asarray(low, dtype=float), 0.0, 1.0)
        predict = np.clip(np.asarray(predict, dtype=float), 0.0, 1.0)
        high = np.clip(np.asarray(high, dtype=float), 0.0, 1.0)
        low = np.minimum(low, predict)
        high = np.maximum(high, predict)
        return low, predict, high
