from __future__ import annotations

from calibrated_explanations.plugins.builtins import PlotSpecDefaultBuilder, PlotSpecDefaultRenderer
from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)
from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

STYLE_ID = "official.example"
BUILDER_ID = "official.visualization.example.builder"
RENDERER_ID = "official.visualization.example.renderer"
BOOTSTRAP_ID = "official.visualization.example.bootstrap"


class ExamplePlotBuilder(PlotBuilder):
    """PlotSpec builder delegating to CE's default PlotSpec builder.

    The important part for new developers is not the drawing logic, but that
    the builder publishes metadata with a stable ``style`` and
    ``default_renderer`` identifier.
    """

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "output_formats": ("png", "svg"),
        "capabilities": ["plot:plotspec"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def __init__(self) -> None:
        self._delegate = PlotSpecDefaultBuilder()

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        return self._delegate.build(context)


class ExamplePlotRenderer(PlotRenderer):
    """PlotSpec renderer delegating to CE's default PlotSpec renderer."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "output_formats": ("png", "svg"),
        "capabilities": ["plot:renderer"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "supports_interactive": False,
    }

    def __init__(self) -> None:
        self._delegate = PlotSpecDefaultRenderer()

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        return self._delegate.render(artifact, context=context)


class ExampleVisualizationBootstrap:
    """Bootstrap entry point that registers the example plot builder, renderer, and style.

    CE auto-discovers the main plugin entry-point group, so visualization
    packages need this bootstrap object to wire builder, renderer, and style
    descriptors into the runtime registry.
    """

    plugin_meta = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "capabilities": ["plot:bootstrap"],
        "trusted": False,
        "trust": False,
    }


def register_example_visualization_components() -> None:
    """Register plot descriptors and style mapping for the visualization example package."""
    if find_plot_builder_descriptor(BUILDER_ID) is None:
        register_plot_builder(BUILDER_ID, ExamplePlotBuilder(), source="entrypoint")
    if find_plot_renderer_descriptor(RENDERER_ID) is None:
        register_plot_renderer(RENDERER_ID, ExamplePlotRenderer(), source="entrypoint")
    if find_plot_style_descriptor(STYLE_ID) is None:
        register_plot_style(
            STYLE_ID,
            metadata={
                "style": STYLE_ID,
                "builder_id": BUILDER_ID,
                "renderer_id": RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )


register_example_visualization_components()
