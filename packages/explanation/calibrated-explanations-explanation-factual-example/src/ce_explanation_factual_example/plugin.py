from __future__ import annotations

from typing import Any

from calibrated_explanations.plugins.builtins import LegacyFactualExplanationPlugin
from calibrated_explanations.plugins.explanations import (
    ExplanationBatch,
    ExplanationContext,
    ExplanationPlugin,
    ExplanationRequest,
)
from calibrated_explanations.plugins.registry import (
    find_explanation_descriptor,
    mark_explanation_trusted,
    register_explanation_plugin,
)


class FactualExampleExplanationPlugin(ExplanationPlugin):
    """Runtime-valid factual explanation plugin delegating to CE's builtin flow.

    This example shows the smallest useful explanation plugin:

    1. publish explanation metadata,
    2. register itself through the explanation descriptor registry,
    3. receive CE's ``ExplanationContext`` during initialization, and
    4. read provisional runtime plugin config from that context before
       forwarding requests to the builtin factual explainer.
    """

    plugin_meta = {
        "schema_version": 1,
        "name": "official.explanation.factual.example",
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "capabilities": ["explain", "explanation:factual", "task:classification"],
        "modes": ("factual",),
        "tasks": ("classification",),
        "dependencies": ("core.interval.legacy", "plot_spec.default"),
        "trusted": True,
        "trust": False,
        "config_schema": {
            "version": 1,
            "additional_properties": False,
            "keys": {
                "label_prefix": {"type": "str", "default": "example"},
                "enabled_labels": {"type": "list[str]", "default": []},
                "diagnostic_token": {
                    "type": "str",
                    "required": False,
                    "sensitive": True,
                },
            },
        },
    }

    def __init__(self) -> None:
        self._delegate = LegacyFactualExplanationPlugin()
        self._last_plugin_config: dict[str, Any] = {}
        self._context: ExplanationContext | None = None

    @property
    def last_plugin_config(self) -> dict[str, Any]:
        """Return the latest provisional runtime plugin config seen by this example."""
        return dict(self._last_plugin_config)

    def supports(self, model: Any) -> bool:
        return self._delegate.supports(model)

    def supports_mode(self, mode: str, *, task: str) -> bool:
        return mode == "factual" and task in self.plugin_meta["tasks"]

    def initialize(self, context: ExplanationContext) -> None:
        """Capture provisional config and CE runtime state through the builtin delegate."""
        self._last_plugin_config = dict(getattr(context, "plugin_config", {}) or {})
        self._context = context
        self._delegate.initialize(context)

    def explain_batch(self, x: Any, request: ExplanationRequest) -> ExplanationBatch:
        """Return a real explanation batch produced by CE's builtin factual flow."""
        if self._context is not None and getattr(self._context, "predict_bridge", None) is not None:
            self._context.predict_bridge.predict(
                x,
                mode="factual",
                task=self._context.task,
                bins=request.bins,
            )
        return self._delegate.explain_batch(x, request)


def register_factual_example_plugin() -> None:
    """Register the example explanation plugin descriptor when imported via entry points."""
    identifier = str(FactualExampleExplanationPlugin.plugin_meta["name"])
    if find_explanation_descriptor(identifier) is not None:
        return
    register_explanation_plugin(
        identifier,
        FactualExampleExplanationPlugin(),
        source="entrypoint",
    )
    mark_explanation_trusted(identifier)


register_factual_example_plugin()
