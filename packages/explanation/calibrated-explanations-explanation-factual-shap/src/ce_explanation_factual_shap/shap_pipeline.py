"""SHAP pipeline for factual SHAP plugin runtime."""

from __future__ import annotations

from typing import Any

import numpy as np
import shap

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
            raise NotImplementedError("Multiclass SHAP factual plugin is not implemented yet.")

        raise RuntimeError("Unexpected SHAP values shape; expected 2D or 3D array.")

    @staticmethod
    def _extract_base_values(shap_explanation: Any) -> np.ndarray:
        base_values = np.asarray(shap_explanation.base_values, dtype=float)

        if base_values.ndim == 0:
            return np.asarray([float(base_values)], dtype=float)

        if base_values.ndim == 1:
            return base_values

        if base_values.ndim == 2:
            if base_values.shape[1] == 1:
                return base_values[:, 0]
            if base_values.shape[1] == 2:
                return base_values[:, 1]

        raise RuntimeError("Unexpected SHAP base_values shape; expected 1D or binary-class 2D.")

    def _normalize_explanation(self, shap_explanation: Any) -> shap.Explanation:
        values = self._extract_feature_values(shap_explanation)
        base_values = self._extract_base_values(shap_explanation)
        data = np.asarray(getattr(shap_explanation, "data", None))

        if data.ndim == 1:
            data = data.reshape(1, -1)

        return shap.Explanation(
            values=values,
            base_values=base_values,
            data=data,
            feature_names=list(self.explainer.feature_names),
        )

    def explain_bounds(
        self,
        x_test: Any,
        *,
        bins: Any | None = None,
        shap_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        raw = self._helper.explain_bounds(
            x_test,
            bins=bins,
            shap_kwargs=shap_kwargs or {},
        )
        result: dict[str, dict[str, Any]] = {}
        for bound_name, bound_explanation in raw.items():
            normalized = self._normalize_explanation(bound_explanation)
            result[bound_name] = {
                "values": np.asarray(normalized.values, dtype=float),
                "base_values": np.asarray(normalized.base_values, dtype=float),
                "raw": normalized,
            }
        return result
