"""SHAP pipeline for factual SHAP plugin runtime."""

from __future__ import annotations

from typing import Any

from calibrated_explanations.utils.exceptions import ConfigurationError

from .shap_helper import ShapHelper


class ShapPipeline:
    """Pipeline for generating SHAP artifacts."""

    def __init__(self, explainer: Any) -> None:
        self.explainer = explainer
        self._shap_helper: ShapHelper | None = None

    def is_shap_enabled(self, is_enabled: bool | None = None) -> bool:
        if self._shap_helper is None:
            self._shap_helper = ShapHelper(self.explainer)
        if is_enabled is not None:
            self._shap_helper.set_enabled(bool(is_enabled))
        return self._shap_helper.is_enabled()

    def preload_shap(self, num_test: int | None = None) -> tuple[Any, Any]:
        if self._shap_helper is None:
            self._shap_helper = ShapHelper(self.explainer)
        return self._shap_helper.preload(num_test=num_test)

    def explain(self, x_test: Any, **kwargs: Any) -> Any:
        shap_explainer, _ = self.preload_shap(num_test=len(x_test))
        if shap_explainer is None:
            raise ConfigurationError(
                "SHAP integration requested but the optional dependency is missing."
            )
        return shap_explainer(x_test, **kwargs)

