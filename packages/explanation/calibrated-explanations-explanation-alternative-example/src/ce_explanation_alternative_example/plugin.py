from __future__ import annotations

from typing import Any

from calibrated_explanations.plugins.builtins import LegacyAlternativeExplanationPlugin
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


class AlternativeExampleExplanationPlugin(ExplanationPlugin):
    """Runtime-valid alternative explanation plugin delegating to CE's builtin flow.

    This companion to the factual example shows the alternative explanation
    wiring explicitly: metadata, descriptor registration, initialization, and
    batch execution all pass through the public plugin interfaces.
    """

    plugin_meta = {
        "schema_version": 1,
        "name": "official.explanation.alternative.example",
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "capabilities": ["explanation:alternative", "task:classification", "explain"],
        "modes": ("alternative",),
        "tasks": ("classification",),
        "dependencies": ("core.interval.legacy", "plot_spec.default"),
        "trusted": False,
        "trust": False,
    }

    def __init__(self) -> None:
        self._delegate = LegacyAlternativeExplanationPlugin()

    def supports(self, model: Any) -> bool:
        return self._delegate.supports(model)

    def supports_mode(self, mode: str, *, task: str) -> bool:
        return self._delegate.supports_mode(mode, task=task)

    def initialize(self, context: ExplanationContext) -> None:
        """Capture CE runtime state through the builtin delegate."""
        self._delegate.initialize(context)

    def explain_batch(self, x: Any, request: ExplanationRequest) -> ExplanationBatch:
        """Return a real alternative explanation batch from CE's builtin flow."""
        return self._delegate.explain_batch(x, request)


def register_alternative_example_plugin() -> None:
    """Register the alternative example explanation descriptor on entry-point load."""
    if find_explanation_descriptor("official.explanation.alternative.example") is not None:
        return
    register_explanation_plugin(
        "official.explanation.alternative.example",
        AlternativeExampleExplanationPlugin(),
        source="entrypoint",
    )


register_alternative_example_plugin()
