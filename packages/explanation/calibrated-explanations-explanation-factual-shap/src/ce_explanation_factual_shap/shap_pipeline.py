"""SHAP pipeline for factual SHAP plugin runtime."""

from __future__ import annotations

from typing import Any

import numpy as np

from .shap_helper import ShapHelper


class ShapPipeline:
    """Pipeline for center/lower/upper/uncertainty SHAP attributions."""

    def __init__(self, explainer: Any) -> None:
        self.explainer = explainer
        self._helper = ShapHelper(explainer)

    @staticmethod
    def _extract_feature_values(shap_explanation: Any) -> np.ndarray:
        values = np.asarray(shap_explanation.values, dtype=float)

        if values.ndim == 2:
            return values

        if values.ndim == 3:
            # Binary classification: use positive class attributions.
            if values.shape[2] == 2:
                return values[:, :, 1]
            raise NotImplementedError(
                "Multiclass SHAP factual plugin is not implemented yet."
            )

        raise RuntimeError("Unexpected SHAP values shape; expected 2D or 3D array.")

    def explain_bounds(
        self,
        x_test: Any,
        *,
        bins: Any | None = None,
        shap_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, np.ndarray]:
        raw = self._helper.explain_bounds(
            x_test,
            bins=bins,
            shap_kwargs=shap_kwargs or {},
        )
        return {
            "center": self._extract_feature_values(raw["center"]),
            "lower": self._extract_feature_values(raw["lower"]),
            "upper": self._extract_feature_values(raw["upper"]),
            "uncertainty": self._extract_feature_values(raw["uncertainty"]),
        }
