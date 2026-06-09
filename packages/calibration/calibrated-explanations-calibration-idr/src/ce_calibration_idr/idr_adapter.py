"""Thin adapter over the upstream :mod:`isodistrreg` Python IDR bindings."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

import numpy as np


@dataclass(frozen=True)
class IDRFitData:
    """One-dimensional IDR calibration scores and targets."""

    scores: np.ndarray
    y: np.ndarray


class IDRDistributionAdapter:
    """Adapter boundary around upstream ``isodistrreg.IDR``.

    The adapter uses the underlying regression learner's scalar prediction as a
    one-dimensional IDR covariate. It intentionally exposes only the CE-facing
    operations needed by the plugin: ``fit``, ``cdf``, and ``quantile``.
    """

    _SUPPORTED_BACKENDS = {"isodistrreg"}

    def __init__(self, *, backend: str = "isodistrreg") -> None:
        """Create an adapter for the upstream ``isodistrreg`` Python bindings."""
        if backend not in self._SUPPORTED_BACKENDS:
            raise ImportError(
                "IDR backend is not installed. Install the upstream isodistrreg Python "
                f"bindings or configure a supported backend. Supported backends: "
                f"{sorted(self._SUPPORTED_BACKENDS)}."
            )
        self.backend = backend
        self._model: Any | None = None
        self._y_min: float | None = None
        self._y_max: float | None = None

    def fit(self, scores: np.ndarray, y: np.ndarray) -> "IDRDistributionAdapter":
        """Fit upstream IDR on scalar calibration scores and observed targets."""
        scores = self._as_1d_float(scores, name="scores")
        y = self._as_1d_float(y, name="y")
        if scores.shape[0] != y.shape[0]:
            raise ValueError("scores and y must have the same number of rows.")
        if scores.shape[0] < 2:
            raise ValueError("IDR calibration requires at least two calibration examples.")

        idr_cls = self._load_idr_class()
        self._y_min = float(np.min(y))
        self._y_max = float(np.max(y))
        self._model = idr_cls(X=scores.reshape(-1, 1), y=y)
        return self

    def cdf(self, scores: np.ndarray, thresholds: np.ndarray | float) -> np.ndarray:
        """Return calibrated CDF values P(Y <= threshold | score)."""
        self._require_fitted()
        scores = self._as_1d_float(scores, name="scores")
        thresholds_arr = np.asarray(thresholds, dtype=float)
        if not np.all(np.isfinite(thresholds_arr)):
            raise ValueError("thresholds must contain only finite values.")
        query_scores = scores.reshape(-1, 1)
        query_thresholds = np.broadcast_to(thresholds_arr, scores.shape)
        model = self._require_fitted()
        if not hasattr(model, "cdf_at"):
            raise TypeError("isodistrreg.IDR must expose cdf_at(covariates, thresholds).")
        values = model.cdf_at(query_scores, query_thresholds)
        return np.clip(np.asarray(values, dtype=float).reshape(scores.shape), 0.0, 1.0)

    def quantile(self, scores: np.ndarray, alpha: float) -> np.ndarray:
        """Return the calibrated alpha quantile for each score."""
        self._require_fitted()
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1].")
        scores = self._as_1d_float(scores, name="scores")
        model = self._require_fitted()
        if not hasattr(model, "quantile"):
            raise TypeError("isodistrreg.IDR must expose quantile(covariates, probabilities).")
        q = np.asarray(model.quantile(scores.reshape(-1, 1), alpha), dtype=float).reshape(-1)
        if self._y_min is not None and self._y_max is not None:
            q = np.clip(q, self._y_min, self._y_max)
        return q

    @staticmethod
    def _load_idr_class() -> type[Any]:
        try:
            module = import_module("isodistrreg")
        except ModuleNotFoundError as exc:
            raise ImportError(
                "The upstream isodistrreg Python bindings are required for IDR calibration. "
                "Install isodistrreg for this Python version before using "
                "IDRRegressionIntervalCalibratorPlugin."
            ) from exc
        idr_cls = getattr(module, "IDR", None)
        if idr_cls is None:
            raise ImportError("The installed isodistrreg package does not expose IDR.")
        return idr_cls

    @staticmethod
    def _as_1d_float(values: np.ndarray, *, name: str) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if arr.ndim == 2 and arr.shape[1] == 1:
            arr = arr[:, 0]
        if arr.ndim != 1:
            raise ValueError(f"{name} must be a one-dimensional array.")
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} must contain only finite values.")
        return arr

    def _require_fitted(self) -> Any:
        if self._model is None:
            raise RuntimeError("IDRDistributionAdapter must be fitted before use.")
        return self._model
