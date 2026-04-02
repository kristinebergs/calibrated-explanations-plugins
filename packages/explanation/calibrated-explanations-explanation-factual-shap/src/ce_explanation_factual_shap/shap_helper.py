"""SHAP helper for factual SHAP plugin runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import shap


@dataclass
class ShapHelper:
    """Build SHAP explainers for center/lower/upper/uncertainty predictions."""

    explainer: Any

    def _background(self) -> Any:
        x_cal = getattr(self.explainer, "x_cal", None)
        if x_cal is None:
            raise RuntimeError("SHAP plugin requires explainer.x_cal but found None.")
        if len(x_cal) == 0:
            raise RuntimeError("SHAP plugin requires non-empty explainer.x_cal.")
        return x_cal

    def _predict_triplet(self, x: Any, *, bins: Any | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        payload = self.explainer.predict(x, uq_interval=True, bins=bins)

        if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[1], tuple):
            center = np.asarray(payload[0], dtype=float)
            lower = np.asarray(payload[1][0], dtype=float)
            upper = np.asarray(payload[1][1], dtype=float)
            return center, lower, upper

        if isinstance(payload, tuple) and len(payload) >= 3:
            center = np.asarray(payload[0], dtype=float)
            lower = np.asarray(payload[1], dtype=float)
            upper = np.asarray(payload[2], dtype=float)
            return center, lower, upper

        raise RuntimeError(
            "Unexpected explainer.predict(..., uq_interval=True) payload shape; "
            "cannot construct lower/upper SHAP explainers."
        )

    def _predict_center(self, x: Any, *, bins: Any | None) -> np.ndarray:
        center, _, _ = self._predict_triplet(x, bins=bins)
        return center

    def _predict_lower(self, x: Any, *, bins: Any | None) -> np.ndarray:
        _, lower, _ = self._predict_triplet(x, bins=bins)
        return lower

    def _predict_upper(self, x: Any, *, bins: Any | None) -> np.ndarray:
        _, _, upper = self._predict_triplet(x, bins=bins)
        return upper

    def _predict_uncertainty(self, x: Any, *, bins: Any | None) -> np.ndarray:
        _, lower, upper = self._predict_triplet(x, bins=bins)
        return upper - lower

    def explain_bounds(
        self,
        x_test: Any,
        *,
        bins: Any | None,
        shap_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        background = self._background()

        center_explainer = shap.Explainer(
            lambda x: self._predict_center(x, bins=bins),
            background,
            feature_names=self.explainer.feature_names,
        )
        lower_explainer = shap.Explainer(
            lambda x: self._predict_lower(x, bins=bins),
            background,
            feature_names=self.explainer.feature_names,
        )
        upper_explainer = shap.Explainer(
            lambda x: self._predict_upper(x, bins=bins),
            background,
            feature_names=self.explainer.feature_names,
        )
        uncertainty_explainer = shap.Explainer(
            lambda x: self._predict_uncertainty(x, bins=bins),
            background,
            feature_names=self.explainer.feature_names,
        )

        return {
            "center": center_explainer(x_test, **shap_kwargs),
            "lower": lower_explainer(x_test, **shap_kwargs),
            "upper": upper_explainer(x_test, **shap_kwargs),
            "uncertainty": uncertainty_explainer(x_test, **shap_kwargs),
        }
