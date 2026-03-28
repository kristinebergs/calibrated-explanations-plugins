"""SHAP helper for factual SHAP plugin runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from calibrated_explanations.utils import safe_import


@dataclass
class ShapHelper:
    """Manage construction and caching of optional SHAP artifacts."""

    explainer: Any
    _enabled: bool = field(default=False, init=False)
    _explainer_instance: Any = field(default=None, init=False)
    _reference_explanation: Any = field(default=None, init=False)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        if not value:
            self.reset()
        else:
            self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def explainer_instance(self) -> Any:
        instance, _ = self.preload()
        return instance

    @explainer_instance.setter
    def explainer_instance(self, value: Any) -> None:
        self._explainer_instance = value

    @property
    def reference_explanation(self) -> Any:
        _, explanation = self.preload()
        return explanation

    @reference_explanation.setter
    def reference_explanation(self, value: Any) -> None:
        self._reference_explanation = value

    def preload(self, num_test: int | None = None) -> tuple[Any, Any]:
        if self._enabled and self._explainer_instance is not None:
            if num_test is None:
                return self._explainer_instance, self._reference_explanation
            shape = getattr(self._reference_explanation, "shape", None)
            if shape is not None and shape[0] == num_test:
                return self._explainer_instance, self._reference_explanation

        try:
            shap_module = safe_import("shap")
        except ImportError:
            self._enabled = False
            return None, None
        if not shap_module:
            return None, None

        x_cal = getattr(self.explainer, "x_cal", None)
        if x_cal is None:
            return None, None
        try:
            if len(x_cal) == 0:
                return None, None
        except TypeError:
            return None, None

        def _predict(x: Any) -> Any:
            return self.explainer.prediction_orchestrator.predict_internal(x)[0]

        self._explainer_instance = shap_module.Explainer(
            _predict,
            x_cal,
            feature_names=self.explainer.feature_names,
        )
        self._reference_explanation = (
            self._explainer_instance(x_cal[0, :].reshape(1, -1))
            if num_test is None
            else self._explainer_instance(x_cal[:num_test, :])
        )
        self._enabled = self._explainer_instance is not None
        return self._explainer_instance, self._reference_explanation

    def reset(self) -> None:
        self._enabled = False
        self._explainer_instance = None
        self._reference_explanation = None

