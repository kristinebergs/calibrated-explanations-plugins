from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calibrated_explanations.plugins.builtins import (
    LegacyFactualExplanationPlugin,
    collection_to_batch,
)
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


class FactualShapExplanationPlugin(ExplanationPlugin):
    """Factual explanation plugin with SHAP artifact enrichment."""

    plugin_meta = {
        "schema_version": 1,
        "name": "official.explanation.factual.shap",
        "version": "0.1.0",
        "provider": "official",
        "capabilities": ['explain', 'explanation:factual', 'task:classification', 'task:regression'],
        "modes": ("factual",),
        "tasks": ('classification', 'regression'),
        "dependencies": ("core.interval.legacy", "plot_spec.default"),
        "trusted": False,
        "trust": False,
    }

    def __init__(self) -> None:
        self._delegate = LegacyFactualExplanationPlugin()
        self._context: ExplanationContext | None = None
        self._pipeline: ShapPipeline | None = None

    def supports(self, model: Any) -> bool:
        return self._delegate.supports(model)

    def supports_mode(self, mode: str, *, task: str) -> bool:
        return self._delegate.supports_mode(mode, task=task)

    def initialize(self, context: ExplanationContext) -> None:
        self._context = context
        self._delegate.initialize(context)
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

        collection = self._context.helper_handles["explainer"].explain_factual(
            x,
            threshold=request.threshold,
            low_high_percentiles=request.low_high_percentiles,
            bins=request.bins,
            features_to_ignore=request.features_to_ignore,
            _use_plugin=False,
        )
        batch = collection_to_batch(collection)

        extras = request.extras if isinstance(request.extras, Mapping) else {}
        shap_kwargs = extras.get("shap_kwargs", {})
        if not isinstance(shap_kwargs, Mapping):
            shap_kwargs = {}

        shap_result = self._pipeline.explain(x, **dict(shap_kwargs))
        batch.collection_metadata["shap"] = {
            "enabled": self._pipeline.is_shap_enabled(),
            "result": shap_result,
        }
        return batch


def register_scaffold_explanation_plugin() -> None:
    if find_explanation_descriptor("official.explanation.factual.shap") is not None:
        return
    register_explanation_plugin("official.explanation.factual.shap", FactualShapExplanationPlugin(), source="entrypoint")


register_scaffold_explanation_plugin()
