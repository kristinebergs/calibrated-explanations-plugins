"""LIME helper for factual LIME plugin runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from calibrated_explanations.utils import safe_import


@dataclass
class LimeHelper:
    """Manage the lifecycle of optional LIME integration artifacts."""

    explainer: Any
    _enabled: bool = field(default=False, init=False)
    _explainer_instance: Any = field(default=None, init=False)
    _reference_explanation: Any = field(default=None, init=False)

    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def set_enabled(self, value: bool) -> None:
        if not value:
            self.reset()
        else:
            self._enabled = True

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

    def preload(self, x_cal: Any = None) -> tuple[Any, Any]:
        if self._enabled and self._explainer_instance is not None:
            return self._explainer_instance, self._reference_explanation

        try:
            lime_cls = safe_import("lime.lime_tabular", "LimeTabularExplainer")
        except ImportError:
            self._enabled = False
            return None, None
        if not lime_cls:
            return None, None

        if not self._enabled or self._explainer_instance is None:
            features = self.explainer.feature_names
            x_cal_source = self.explainer.x_cal[:1, :] if x_cal is None else x_cal
            if self.explainer.mode == "classification":
                self._explainer_instance = lime_cls(
                    x_cal_source,
                    feature_names=features,
                    class_names=["0", "1"],
                    mode=self.explainer.mode,
                )
                self._reference_explanation = self._explainer_instance.explain_instance(
                    self.explainer.x_cal[0, :],
                    self.explainer.learner.predict_proba,
                    num_features=self.explainer.num_features,
                )
            elif "regression" in self.explainer.mode:
                self._explainer_instance = lime_cls(
                    x_cal_source,
                    feature_names=features,
                    mode="regression",
                )
                self._reference_explanation = self._explainer_instance.explain_instance(
                    self.explainer.x_cal[0, :],
                    self.explainer.learner.predict,
                    num_features=self.explainer.num_features,
                )
            self._enabled = self._explainer_instance is not None

        return self._explainer_instance, self._reference_explanation

    def reset(self) -> None:
        self._enabled = False
        self._explainer_instance = None
        self._reference_explanation = None
