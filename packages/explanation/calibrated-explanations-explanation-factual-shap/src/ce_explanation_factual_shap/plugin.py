from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from calibrated_explanations.plugins.builtins import collection_to_batch
from calibrated_explanations.plugins.explanations import (
    ExplanationBatch,
    ExplanationContext,
    ExplanationPlugin,
    ExplanationRequest,
)
from calibrated_explanations.plugins.registry import (
    find_explanation_descriptor,
    register_explanation_plugin,
)

from .shap_pipeline import ShapPipeline


def _to_float_matrix(values: Any) -> list[list[float]]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2:
        raise RuntimeError("Uncertainty SHAP metadata must be a 2D matrix.")
    return [[float(value) for value in row] for row in array]


class FactualShapExplanationPlugin(ExplanationPlugin):
    """Factual explanation plugin producing SHAP-based feature attributions."""

    plugin_meta = {
        "schema_version": 1,
        "name": "official.explanation.factual.shap",
        "version": "0.1.0",
        "provider": "official",
        "capabilities": [
            "explain",
            "explanation:factual",
            "task:classification",
            "task:regression",
        ],
        "modes": ("factual",),
        "tasks": ("classification", "regression"),
        "dependencies": ("core.interval.legacy", "plot_spec.default"),
        "trusted": False,
        "trust": False,
    }

    def __init__(self) -> None:
        self._context: ExplanationContext | None = None
        self._pipeline: ShapPipeline | None = None

    def supports(self, model: Any) -> bool:
        return (
            hasattr(model, "prediction_orchestrator")
            and hasattr(model, "explain_fast")
            and hasattr(model, "predict")
        )

    def supports_mode(self, mode: str, *, task: str) -> bool:
        return mode == "factual" and task in self.plugin_meta["tasks"]

    def initialize(self, context: ExplanationContext) -> None:
        self._context = context
        explainer_handle = context.helper_handles.get("explainer")
        if explainer_handle is None:
            raise RuntimeError("Explanation context missing required 'explainer' handle.")
        self._pipeline = ShapPipeline(explainer_handle)

    def explain_batch(self, x: Any, request: ExplanationRequest) -> ExplanationBatch:
        if self._context is None or self._pipeline is None:
            raise RuntimeError("Plugin must be initialized before use.")

        self._context.predict_bridge.predict(
            x,
            mode="factual",
            task=self._context.task,
            bins=request.bins,
        )

        explainer = self._context.helper_handles["explainer"]
        collection = explainer.explain_factual(
            x,
            threshold=request.threshold,
            low_high_percentiles=request.low_high_percentiles or (5, 95),
            bins=request.bins,
            _use_plugin=False,
        )

        extras = request.extras if isinstance(request.extras, Mapping) else {}
        shap_kwargs = extras.get("shap_kwargs", {})
        if not isinstance(shap_kwargs, Mapping):
            shap_kwargs = {}

        contributions = self._pipeline.explain_bounds(
            x_test=x,
            bins=request.bins,
            shap_kwargs=dict(shap_kwargs),
        )
        center_matrix = np.asarray(contributions["center"], dtype=float)
        lower_matrix = np.asarray(contributions["lower"], dtype=float)
        upper_matrix = np.asarray(contributions["upper"], dtype=float)
        uncertainty_matrix = np.asarray(contributions["uncertainty"], dtype=float)

        feature_names = list(self._context.feature_names)
        for row_index, explanation in enumerate(collection.explanations):
            rules = explanation.get_rules()
            features = list(rules.get("feature", []))
            labels = [feature_names[feature] for feature in features]
            center_weights = [float(center_matrix[row_index, feature]) for feature in features]
            lower_weights = [float(lower_matrix[row_index, feature]) for feature in features]
            upper_weights = [float(upper_matrix[row_index, feature]) for feature in features]

            rules["rule"] = labels
            rules["weight"] = center_weights
            rules["weight_low"] = lower_weights
            rules["weight_high"] = upper_weights

            base_predict = float(rules["base_predict"][0]) if rules.get("base_predict") else 0.0
            base_predict_low = float(rules["base_predict_low"][0]) if rules.get("base_predict_low") else 0.0
            base_predict_high = float(rules["base_predict_high"][0]) if rules.get("base_predict_high") else 0.0
            rules["predict"] = [base_predict + weight for weight in center_weights]
            rules["predict_low"] = [base_predict_low + weight for weight in lower_weights]
            rules["predict_high"] = [base_predict_high + weight for weight in upper_weights]

            explanation.rules = rules

        batch = collection_to_batch(collection)
        batch.collection_metadata["shap"] = {
            "enabled": True,
            "lower_upper_attributions": True,
            "uncertainty_attributions": {
                "enabled": True,
                "target": "interval_width",
                "formula": "upper - lower",
                "feature_names": feature_names,
                "values": _to_float_matrix(uncertainty_matrix),
            },
        }
        return batch


def register_scaffold_explanation_plugin() -> None:
    if find_explanation_descriptor("official.explanation.factual.shap") is not None:
        return
    register_explanation_plugin(
        "official.explanation.factual.shap",
        FactualShapExplanationPlugin(),
        source="entrypoint",
    )


register_scaffold_explanation_plugin()
