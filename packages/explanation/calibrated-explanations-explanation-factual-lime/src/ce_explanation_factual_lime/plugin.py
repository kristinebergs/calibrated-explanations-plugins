from __future__ import annotations

from typing import Any

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

from .lime_pipeline import LimePipeline


class FactualLimeExplanationPlugin(ExplanationPlugin):
    """Factual explanation plugin backed by migrated LIME pipeline logic."""

    plugin_meta = {
        "schema_version": 1,
        "name": "official.explanation.factual.lime",
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
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
        self._pipeline: LimePipeline | None = None

    def supports(self, model: Any) -> bool:
        return hasattr(model, "prediction_orchestrator") and hasattr(model, "explain_factual")

    def supports_mode(self, mode: str, *, task: str) -> bool:
        return mode == "factual" and task in self.plugin_meta["tasks"]

    def initialize(self, context: ExplanationContext) -> None:
        self._context = context
        explainer_handle = context.helper_handles.get("explainer")
        if explainer_handle is None:
            raise RuntimeError("Explanation context missing required 'explainer' handle.")
        self._pipeline = LimePipeline(explainer_handle)

    def explain_batch(self, x: Any, request: ExplanationRequest) -> ExplanationBatch:
        if self._context is None or self._pipeline is None:
            raise RuntimeError("Plugin must be initialized before use.")

        self._context.predict_bridge.predict(
            x,
            mode="factual",
            task=self._context.task,
            bins=request.bins,
        )

        collection = self._pipeline.explain(
            x_test=x,
            threshold=request.threshold,
            low_high_percentiles=request.low_high_percentiles or (5, 95),
            bins=request.bins,
        )
        batch = collection_to_batch(collection)
        batch.collection_metadata["lime"] = {"enabled": True}
        return batch


def register_scaffold_explanation_plugin() -> None:
    if find_explanation_descriptor("official.explanation.factual.lime") is not None:
        return
    register_explanation_plugin(
        "official.explanation.factual.lime", FactualLimeExplanationPlugin(), source="entrypoint"
    )


register_scaffold_explanation_plugin()
