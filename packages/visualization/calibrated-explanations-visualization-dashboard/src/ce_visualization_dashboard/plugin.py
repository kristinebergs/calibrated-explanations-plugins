from __future__ import annotations

import warnings
from pathlib import Path
from types import MappingProxyType
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)
from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_plugin,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

from . import layout as _layout

STYLE_ID = "official.visualization.dashboard"
BUILDER_ID = "official.visualization.dashboard.builder"
RENDERER_ID = "official.visualization.dashboard.renderer"
BOOTSTRAP_ID = "official.visualization.dashboard.bootstrap"

# Sub-style that renders CE's native plot.
# Include it in a plots spec as {"style": CE_DEFAULT_STYLE_ID}.
CE_DEFAULT_STYLE_ID = "official.visualization.dashboard.ce_default"
CE_DEFAULT_BUILDER_ID = "official.visualization.dashboard.ce_default.builder"
CE_DEFAULT_RENDERER_ID = "official.visualization.dashboard.ce_default.renderer"


def _as_save_paths(
    base_path: str | None,
    save_ext: str | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if not base_path or not save_ext:
        return ()
    suffixes = (save_ext,) if isinstance(save_ext, str) else tuple(save_ext)
    stem = Path(base_path)
    paths = []
    for suffix in suffixes:
        ext = suffix if str(suffix).startswith(".") else f".{suffix}"
        paths.append(str(stem.with_suffix(ext)))
    return tuple(paths)


class DashboardPlotBuilder(PlotBuilder):
    """Build dashboard artifacts by validating registered sub-plot styles."""

    plugin_meta: dict[str, Any] = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "output_formats": ("html", "png"),
        "capabilities": ["plot:dashboard"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        options = dict(context.options)
        plots: list[dict[str, Any]] = list(options.get("plots") or [])
        narrative: bool = bool(options.get("narrative", True))
        expertise_level: str = str(options.get("expertise_level", "beginner"))
        title: str | None = options.get("title")
        strict_subplots: bool = bool(options.get("strict_subplots", False))
        # per_instance=True (default): one dashboard per instance when a collection
        # is passed, each with its own panels and narrative for that instance.
        # per_instance=False: one dashboard for the whole collection.
        per_instance: bool = bool(options.get("per_instance", True))

        # Validate all requested styles are registered
        for plot_spec in plots:
            style = plot_spec.get("style")
            if not style:
                raise RuntimeError(
                    "Each entry in 'plots' must have a 'style' key with a registered style ID."
                )
            if find_plot_style_descriptor(str(style)) is None:
                raise RuntimeError(
                    f"Plot style {style!r} is not registered. "
                    "Ensure the corresponding plugin package is installed and loaded."
                )

        return {
            "explanation": context.explanation,
            "plots": plots,
            "narrative": narrative,
            "expertise_level": expertise_level,
            "title": title,
            "per_instance": per_instance,
            "strict_subplots": strict_subplots,
        }


def _render_panels(
    plots: list[dict[str, Any]],
    explanation: Any,
    context: PlotRenderContext,
    *,
    strict_subplots: bool = False,
) -> list[bytes]:
    """Render sub-plot panels for *explanation*, returning a list of PNG bytes."""
    panel_bytes: list[bytes] = []
    for plot_spec in plots:
        style = str(plot_spec["style"])
        sub_options = {k: v for k, v in plot_spec.items() if k != "style"}
        plugin = find_plot_plugin(style)
        if plugin is None:
            if strict_subplots:
                raise RuntimeError(f"Style {style!r} not found in registry.")
            panel_bytes.append(
                _layout.error_placeholder_bytes(f"Style {style!r} not found in registry.")
            )
            continue
        sub_context = PlotRenderContext(
            explanation=explanation,
            instance_metadata=context.instance_metadata,
            style=style,
            intent=context.intent,
            show=False,
            path=None,
            save_ext=None,
            options=MappingProxyType(sub_options),
        )
        try:
            sub_artifact = plugin.build(sub_context)
            sub_result = plugin.render(sub_artifact, context=sub_context)
            if sub_result.figure is not None:
                panel_bytes.append(_layout.figure_to_png_bytes(sub_result.figure))
            for extra_fig in sub_result.extras.get("extra_figures", []):
                panel_bytes.append(_layout.figure_to_png_bytes(extra_fig))
        except Exception as exc:  # noqa: BLE001
            if strict_subplots:
                raise
            panel_bytes.append(_layout.error_placeholder_bytes(str(exc)))
    return panel_bytes


def _build_narrative_text(
    narrative: bool,
    explanation: Any,
    expertise_level: str,
) -> str | None:
    """Return narrative text for *explanation*, or ``None`` if narrative is disabled."""
    if not narrative:
        return None
    try:
        return _layout.render_narrative_panel(explanation, expertise_level)
    except Exception as exc:  # noqa: BLE001
        return f"Narrative unavailable: {exc}"


def _build_combined_narrative(
    narrative: bool,
    explanation: Any,
    expertise_level: str,
) -> str | list[str] | None:
    """Return narrative content for combined dashboards."""
    if not narrative:
        return None
    collection = getattr(explanation, "explanations", None)
    if collection is None:
        return _build_narrative_text(True, explanation, expertise_level)

    narratives: list[str] = []
    for single_exp in collection:
        single_narrative = _build_narrative_text(True, single_exp, expertise_level)
        narratives.append(single_narrative or "")
    return narratives


def _save_figure(fig: Any, save_path: str) -> bool:
    """Save *fig* to *save_path*. Returns True on success."""
    if save_path.endswith(".png"):
        try:
            fig.write_image(save_path)
            return True
        except Exception:  # noqa: BLE001
            warnings.warn(
                f"Could not save dashboard as PNG to {save_path!r}. "
                "Install 'kaleido' to enable PNG export: pip install kaleido",
                UserWarning,
                stacklevel=3,
            )
            return False
    # .html or unknown — write HTML
    fig.write_html(save_path)
    return True


class DashboardPlotRenderer(PlotRenderer):
    """Render a multi-panel plotly dashboard by delegating to registered sub-plugins."""

    plugin_meta: dict[str, Any] = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "output_formats": ("html", "png"),
        "capabilities": ["plot:renderer", "plot:dashboard"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "supports_interactive": True,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        payload = dict(artifact)
        explanation = payload["explanation"]
        plots: list[dict[str, Any]] = list(payload.get("plots") or [])
        narrative: bool = bool(payload.get("narrative", True))
        expertise_level: str = str(payload.get("expertise_level", "beginner"))
        title: str | None = payload.get("title")
        per_instance: bool = bool(payload.get("per_instance", True))
        strict_subplots: bool = bool(payload.get("strict_subplots", False))

        collection = getattr(explanation, "explanations", None)

        if collection is not None and per_instance:
            return self._render_per_instance(
                artifact,
                context,
                collection,
                plots,
                narrative,
                expertise_level,
                title,
                strict_subplots,
            )
        return self._render_combined(
            artifact,
            context,
            explanation,
            plots,
            narrative,
            expertise_level,
            title,
            strict_subplots,
        )

    def _render_per_instance(
        self,
        artifact: PlotArtifact,
        context: PlotRenderContext,
        collection: list[Any],
        plots: list[dict[str, Any]],
        narrative: bool,
        expertise_level: str,
        title: str | None,
        strict_subplots: bool,
    ) -> PlotRenderResult:
        """One dashboard figure per instance; narrative is per-instance."""
        figs: list[Any] = []
        n_panels_last = 0
        for single_exp in collection:
            panels = _render_panels(plots, single_exp, context, strict_subplots=strict_subplots)
            n_panels_last = len(panels)
            narr = _build_narrative_text(narrative, single_exp, expertise_level)
            figs.append(_layout.assemble_dashboard(panels, narr, title))

        if not figs:
            figs = [_layout.assemble_dashboard([], None, title)]

        # Save: suffix each file with _0, _1, … when multiple instances
        saved = self._save_per_instance(figs, context)

        return PlotRenderResult(
            artifact=artifact,
            figure=figs[0],
            saved_paths=tuple(saved),
            extras={
                "n_panels": n_panels_last,
                "narrative": narrative,
                "extra_figures": figs[1:],
                "n_instances": len(figs),
            },
        )

    def _render_combined(
        self,
        artifact: PlotArtifact,
        context: PlotRenderContext,
        explanation: Any,
        plots: list[dict[str, Any]],
        narrative: bool,
        expertise_level: str,
        title: str | None,
        strict_subplots: bool,
    ) -> PlotRenderResult:
        """One dashboard figure for the whole explanation (or single instance)."""
        panels = _render_panels(plots, explanation, context, strict_subplots=strict_subplots)
        narr = _build_combined_narrative(narrative, explanation, expertise_level)
        fig = _layout.assemble_dashboard(panels, narr, title)

        saved: list[str] = []
        for save_path in _as_save_paths(context.path, context.save_ext):
            if _save_figure(fig, save_path):
                saved.append(save_path)

        return PlotRenderResult(
            artifact=artifact,
            figure=fig,
            saved_paths=tuple(saved),
            extras={"n_panels": len(panels), "narrative": narrative},
        )

    def _save_per_instance(
        self,
        figs: list[Any],
        context: PlotRenderContext,
    ) -> list[str]:
        """Save per-instance figures, suffixing paths with _0, _1, … if needed."""
        raw_paths = _as_save_paths(context.path, context.save_ext)
        if not raw_paths:
            return []
        saved: list[str] = []
        for raw_path in raw_paths:
            stem = Path(raw_path)
            suffix = stem.suffix
            base = str(stem.with_suffix(""))
            if len(figs) == 1:
                if _save_figure(figs[0], raw_path):
                    saved.append(raw_path)
            else:
                for i, fig in enumerate(figs):
                    inst_path = f"{base}_{i}{suffix}"
                    if _save_figure(fig, inst_path):
                        saved.append(inst_path)
        return saved


class CeDefaultPlotBuilder(PlotBuilder):
    """Build artifact for CE's native plot, mirroring how CE's own plot() works.

    When the explanation is a single instance, one panel is produced.
    When the explanation is a collection, one panel per instance is produced —
    the same behaviour as calling ``explanations.plot()`` in CE directly.

    Instance selection follows CE's own convention: index the collection
    *before* calling plot (e.g. ``explanations[0].plot(...)``), not via an
    ``instance_index`` option inside the plots spec.
    """

    plugin_meta: dict[str, Any] = {
        "schema_version": 1,
        "name": CE_DEFAULT_BUILDER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "style": CE_DEFAULT_STYLE_ID,
        "output_formats": ("png",),
        "capabilities": ["plot:ce_default"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": CE_DEFAULT_RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        options = dict(context.options)
        plot_kwargs = dict(options)
        # ``style`` is consumed by the dashboard routing layer; use ``ce_style``
        # to forward CE's own style parameter (e.g. "ensured", "triangular").
        ce_style = plot_kwargs.pop("ce_style", None)
        if ce_style is not None:
            plot_kwargs["style"] = ce_style
        return {
            "explanation": context.explanation,
            "plot_kwargs": plot_kwargs,
        }


class CeDefaultPlotRenderer(PlotRenderer):
    """Render CE's native plot via ``explanation.plot(show=False)``.

    Always receives exactly one explanation object (single instance or collection).
    The dashboard's ``per_instance`` routing ensures that when iterating a
    collection each instance is passed individually; the renderer just calls
    ``explanation.plot(show=False)`` and captures the resulting figure.
    """

    plugin_meta: dict[str, Any] = {
        "schema_version": 1,
        "name": CE_DEFAULT_RENDERER_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "output_formats": ("png",),
        "capabilities": ["plot:renderer"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "supports_interactive": False,
    }

    def render(  # pylint: disable=unused-argument
        self,
        artifact: PlotArtifact,
        *,
        context: PlotRenderContext,
    ) -> PlotRenderResult:
        import matplotlib.pyplot as plt

        payload = dict(artifact)
        explanation = payload["explanation"]
        plot_kwargs: dict[str, Any] = dict(payload.get("plot_kwargs") or {})

        collection = getattr(explanation, "explanations", None)
        if collection is not None:
            # Collection: render each instance individually so plt.gcf() is unambiguous.
            figs = []
            for single_exp in collection:
                plt.figure()
                single_exp.plot(show=False, **plot_kwargs)
                figs.append(plt.gcf())
            if not figs:
                return PlotRenderResult(
                    artifact=artifact, figure=plt.figure(), saved_paths=(), extras={}
                )
            return PlotRenderResult(
                artifact=artifact,
                figure=figs[0],
                saved_paths=(),
                extras={"extra_figures": figs[1:]},
            )
        # Single instance — existing behaviour.
        plt.figure()
        explanation.plot(show=False, **plot_kwargs)
        fig = plt.gcf()

        return PlotRenderResult(
            artifact=artifact,
            figure=fig,
            saved_paths=(),
            extras={},
        )


class DashboardVisualizationBootstrap:
    """Bootstrap entry point for the dashboard visualization plugin package."""

    plugin_meta: dict[str, Any] = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": "0.1.0",
        "provider": "official",
        "data_modalities": ("tabular",),
        "capabilities": ["plot:bootstrap"],
        "trusted": False,
        "trust": False,
    }


def register_dashboard_visualization_components() -> None:
    """Register the dashboard visualization builder, renderer, and style."""
    if find_plot_builder_descriptor(BUILDER_ID) is None:
        register_plot_builder(BUILDER_ID, DashboardPlotBuilder(), source="entrypoint")
    if find_plot_renderer_descriptor(RENDERER_ID) is None:
        register_plot_renderer(RENDERER_ID, DashboardPlotRenderer(), source="entrypoint")
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
    # CE-native single-instance sub-plot style (factual & alternative)
    if find_plot_builder_descriptor(CE_DEFAULT_BUILDER_ID) is None:
        register_plot_builder(CE_DEFAULT_BUILDER_ID, CeDefaultPlotBuilder(), source="entrypoint")
    if find_plot_renderer_descriptor(CE_DEFAULT_RENDERER_ID) is None:
        register_plot_renderer(CE_DEFAULT_RENDERER_ID, CeDefaultPlotRenderer(), source="entrypoint")
    if find_plot_style_descriptor(CE_DEFAULT_STYLE_ID) is None:
        register_plot_style(
            CE_DEFAULT_STYLE_ID,
            metadata={
                "style": CE_DEFAULT_STYLE_ID,
                "builder_id": CE_DEFAULT_BUILDER_ID,
                "renderer_id": CE_DEFAULT_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )


register_dashboard_visualization_components()
