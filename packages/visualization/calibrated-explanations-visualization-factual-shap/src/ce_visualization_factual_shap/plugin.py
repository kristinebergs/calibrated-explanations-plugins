from __future__ import annotations

from pathlib import Path
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderResult,
    PlotRenderer,
)
from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

from .adapter import get_shap_metadata, plot_shap


STYLE_ID = "official.visualization.factual.shap"
BUILDER_ID = "official.visualization.factual.shap.builder"
RENDERER_ID = "official.visualization.factual.shap.renderer"
BOOTSTRAP_ID = "official.visualization.factual.shap.bootstrap"
_CE_ONLY_PLOT_OPTIONS = {
    "filename",
    "renderer",
    "return_plot_spec",
    "rnk_metric",
    "rnk_weight",
    "show",
    "style",
    "uncertainty",
    "use_legacy",
}


def _as_save_paths(base_path: str | None, save_ext: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if not base_path or not save_ext:
        return ()
    suffixes = (save_ext,) if isinstance(save_ext, str) else tuple(save_ext)
    stem = Path(base_path)
    paths = []
    for suffix in suffixes:
        ext = suffix if str(suffix).startswith(".") else f".{suffix}"
        paths.append(str(stem.with_suffix(ext)))
    return tuple(paths)


class FactualShapPlotBuilder(PlotBuilder):
    """Build runtime artifacts for SHAP-backed visualization rendering."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": "0.1.0",
        "provider": "official",
        "style": STYLE_ID,
        "output_formats": ("png", "svg"),
        "capabilities": ["plot:plotspec"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        _ = get_shap_metadata(context.explanation)
        options = dict(context.options)
        return {
            "explanation": context.explanation,
            "shap_kind": options.get("shap_kind", "bar"),
            "shap_bound": options.get("shap_bound", "center"),
            "instance_index": options.get("instance_index"),
            "prefer_runtime": bool(options.get("prefer_runtime", True)),
            "plot_kwargs": {
                key: value
                for key, value in options.items()
                if key not in {"shap_kind", "shap_bound", "instance_index", "prefer_runtime"}
                and key not in _CE_ONLY_PLOT_OPTIONS
            },
        }


class FactualShapPlotRenderer(PlotRenderer):
    """Renderer dispatching to SHAP's native plotting helpers."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": "0.1.0",
        "provider": "official",
        "output_formats": ("png", "svg"),
        "capabilities": ["plot:renderer"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "supports_interactive": False,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        payload = dict(artifact)
        figure = plot_shap(
            payload["explanation"],
            kind=str(payload["shap_kind"]),
            bound=str(payload["shap_bound"]),
            instance_index=payload.get("instance_index"),
            prefer_runtime=bool(payload.get("prefer_runtime", True)),
            show=context.show,
            **dict(payload.get("plot_kwargs", {})),
        )

        saved_paths = _as_save_paths(context.path, context.save_ext)
        for save_path in saved_paths:
            figure.savefig(save_path)

        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={
                "shap_kind": payload["shap_kind"],
                "shap_bound": payload["shap_bound"],
            },
        )


class FactualShapVisualizationBootstrap:
    """Bootstrap entry point for the factual SHAP visualization plugin package."""

    plugin_meta = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": "0.1.0",
        "provider": "official",
        "capabilities": ["plot:bootstrap"],
        "trusted": False,
        "trust": False,
    }


def register_factual_shap_visualization_components() -> None:
    """Register the factual SHAP visualization builder, renderer, and style."""
    if find_plot_builder_descriptor(BUILDER_ID) is None:
        register_plot_builder(BUILDER_ID, FactualShapPlotBuilder(), source="entrypoint")
    if find_plot_renderer_descriptor(RENDERER_ID) is None:
        register_plot_renderer(RENDERER_ID, FactualShapPlotRenderer(), source="entrypoint")
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


register_factual_shap_visualization_components()
