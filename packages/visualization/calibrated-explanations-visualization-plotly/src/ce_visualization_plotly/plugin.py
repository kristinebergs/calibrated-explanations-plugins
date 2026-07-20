from __future__ import annotations

from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

from ._version import PACKAGE_VERSION, PROVIDER
from .alternative_bars import (
    BUILDER_ID as ALTERNATIVE_BARS_BUILDER_ID,
)
from .alternative_bars import (
    RENDERER_ID as ALTERNATIVE_BARS_RENDERER_ID,
)
from .alternative_bars import (
    STYLE_ID as ALTERNATIVE_BARS_STYLE_ID,
)
from .alternative_bars import (
    LocalAlternativeBarsPlotBuilder,
    LocalAlternativeBarsPlotRenderer,
)
from .alternative_feature_summary import (
    BUILDER_ID as ALTERNATIVE_FEATURE_SUMMARY_BUILDER_ID,
)
from .alternative_feature_summary import (
    RENDERER_ID as ALTERNATIVE_FEATURE_SUMMARY_RENDERER_ID,
)
from .alternative_feature_summary import (
    STYLE_ID as ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
)
from .alternative_feature_summary import (
    AlternativeFeatureSummaryPlotBuilder,
    AlternativeFeatureSummaryPlotRenderer,
)
from .ensured import (
    ALIAS_STYLE_ID as ENSURED_ALIAS_STYLE_ID,
)
from .ensured import (
    BUILDER_ID as ENSURED_BUILDER_ID,
)
from .ensured import (
    RENDERER_ID as ENSURED_RENDERER_ID,
)
from .ensured import (
    STYLE_ID as ENSURED_STYLE_ID,
)
from .ensured import (
    LocalEnsuredPlotBuilder,
    LocalEnsuredPlotRenderer,
)
from .factual_bars import (
    BUILDER_ID as FACTUAL_BARS_BUILDER_ID,
)
from .factual_bars import (
    RENDERER_ID as FACTUAL_BARS_RENDERER_ID,
)
from .factual_bars import (
    STYLE_ID as FACTUAL_BARS_STYLE_ID,
)
from .factual_bars import (
    LocalFactualBarsPlotBuilder,
    LocalFactualBarsPlotRenderer,
)
from .factual_simple import (
    BUILDER_ID as FACTUAL_SIMPLE_BUILDER_ID,
)
from .factual_simple import (
    RENDERER_ID as FACTUAL_SIMPLE_RENDERER_ID,
)
from .factual_simple import (
    STYLE_ID as FACTUAL_SIMPLE_STYLE_ID,
)
from .factual_simple import (
    LocalFactualSimplePlotBuilder,
    LocalFactualSimplePlotRenderer,
)
from .instance_explorer import (
    BUILDER_ID as INSTANCE_EXPLORER_BUILDER_ID,
)
from .instance_explorer import (
    RENDERER_ID as INSTANCE_EXPLORER_RENDERER_ID,
)
from .instance_explorer import (
    STYLE_ID as INSTANCE_EXPLORER_STYLE_ID,
)
from .instance_explorer import (
    GlobalInstanceExplorerPlotBuilder,
    GlobalInstanceExplorerPlotRenderer,
)
from .instance_workspace import (
    BUILDER_ID as INSTANCE_WORKSPACE_BUILDER_ID,
)
from .instance_workspace import (
    RENDERER_ID as INSTANCE_WORKSPACE_RENDERER_ID,
)
from .instance_workspace import (
    STYLE_ID as INSTANCE_WORKSPACE_STYLE_ID,
)
from .instance_workspace import (
    InstanceWorkspaceDashboardBuilder,
    InstanceWorkspaceDashboardRenderer,
)
from .quadrant import (
    BUILDER_ID,
    RENDERER_ID,
    STYLE_ID,
    UncertaintyQuadrantPlotBuilder,
    UncertaintyQuadrantPlotRenderer,
)

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"


class PlotlyVisualizationBootstrap:
    """Bootstrap entry point for Plotly visualization layouts.

    CE 1.0.x entry-point discovery loads and validates this class but does not
    invoke anything on it, so discovery alone does not register the styles.
    Hosts that want the styles must call :meth:`register` (equivalently
    ``register_plotly_visualization_components()``) explicitly.
    """

    @staticmethod
    def register() -> None:
        """Register all Plotly styles through CE's public plot-plugin contract."""
        register_plotly_visualization_components()

    plugin_meta = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": PACKAGE_VERSION,
        "provider": PROVIDER,
        "data_modalities": ("tabular",),
        # Capability vocabulary follows CE's own builtins
        # (calibrated_explanations.plugins.builtins uses "plot:builder" /
        # "plot:renderer"); this bootstrap provides components of both kinds.
        "capabilities": ["plot:builder", "plot:renderer"],
        "trusted": False,
        "trust": False,
    }


def register_plotly_visualization_components() -> None:
    """Register Plotly visualization builders, renderers, and styles.

    This is an explicit call — importing ``ce_visualization_plotly`` (or this
    module) has no registration or CE-patching side effects. Registration is
    idempotent.

    CE >=1.0.0rc2 dispatches explicit third-party styles natively through the
    public registry with the complete option set and (for trusted plugins) a
    documented runtime context, so no compatibility bridge is installed and
    no CE plotting callable is ever replaced.
    """
    if find_plot_builder_descriptor(BUILDER_ID) is None:
        register_plot_builder(BUILDER_ID, UncertaintyQuadrantPlotBuilder(), source="entrypoint")
    if find_plot_renderer_descriptor(RENDERER_ID) is None:
        register_plot_renderer(RENDERER_ID, UncertaintyQuadrantPlotRenderer(), source="entrypoint")
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
    if find_plot_builder_descriptor(ENSURED_BUILDER_ID) is None:
        register_plot_builder(
            ENSURED_BUILDER_ID,
            LocalEnsuredPlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(ENSURED_RENDERER_ID) is None:
        register_plot_renderer(
            ENSURED_RENDERER_ID,
            LocalEnsuredPlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(ENSURED_STYLE_ID) is None:
        register_plot_style(
            ENSURED_STYLE_ID,
            metadata={
                "style": ENSURED_STYLE_ID,
                "builder_id": ENSURED_BUILDER_ID,
                "renderer_id": ENSURED_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_style_descriptor(ENSURED_ALIAS_STYLE_ID) is None:
        register_plot_style(
            ENSURED_ALIAS_STYLE_ID,
            metadata={
                "style": ENSURED_ALIAS_STYLE_ID,
                "builder_id": ENSURED_BUILDER_ID,
                "renderer_id": ENSURED_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(FACTUAL_BARS_BUILDER_ID) is None:
        register_plot_builder(
            FACTUAL_BARS_BUILDER_ID,
            LocalFactualBarsPlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(FACTUAL_BARS_RENDERER_ID) is None:
        register_plot_renderer(
            FACTUAL_BARS_RENDERER_ID,
            LocalFactualBarsPlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(FACTUAL_BARS_STYLE_ID) is None:
        register_plot_style(
            FACTUAL_BARS_STYLE_ID,
            metadata={
                "style": FACTUAL_BARS_STYLE_ID,
                "builder_id": FACTUAL_BARS_BUILDER_ID,
                "renderer_id": FACTUAL_BARS_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(FACTUAL_SIMPLE_BUILDER_ID) is None:
        register_plot_builder(
            FACTUAL_SIMPLE_BUILDER_ID,
            LocalFactualSimplePlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(FACTUAL_SIMPLE_RENDERER_ID) is None:
        register_plot_renderer(
            FACTUAL_SIMPLE_RENDERER_ID,
            LocalFactualSimplePlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(FACTUAL_SIMPLE_STYLE_ID) is None:
        register_plot_style(
            FACTUAL_SIMPLE_STYLE_ID,
            metadata={
                "style": FACTUAL_SIMPLE_STYLE_ID,
                "builder_id": FACTUAL_SIMPLE_BUILDER_ID,
                "renderer_id": FACTUAL_SIMPLE_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(ALTERNATIVE_FEATURE_SUMMARY_BUILDER_ID) is None:
        register_plot_builder(
            ALTERNATIVE_FEATURE_SUMMARY_BUILDER_ID,
            AlternativeFeatureSummaryPlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(ALTERNATIVE_FEATURE_SUMMARY_RENDERER_ID) is None:
        register_plot_renderer(
            ALTERNATIVE_FEATURE_SUMMARY_RENDERER_ID,
            AlternativeFeatureSummaryPlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID) is None:
        register_plot_style(
            ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
            metadata={
                "style": ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
                "builder_id": ALTERNATIVE_FEATURE_SUMMARY_BUILDER_ID,
                "renderer_id": ALTERNATIVE_FEATURE_SUMMARY_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(ALTERNATIVE_BARS_BUILDER_ID) is None:
        register_plot_builder(
            ALTERNATIVE_BARS_BUILDER_ID,
            LocalAlternativeBarsPlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(ALTERNATIVE_BARS_RENDERER_ID) is None:
        register_plot_renderer(
            ALTERNATIVE_BARS_RENDERER_ID,
            LocalAlternativeBarsPlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(ALTERNATIVE_BARS_STYLE_ID) is None:
        register_plot_style(
            ALTERNATIVE_BARS_STYLE_ID,
            metadata={
                "style": ALTERNATIVE_BARS_STYLE_ID,
                "builder_id": ALTERNATIVE_BARS_BUILDER_ID,
                "renderer_id": ALTERNATIVE_BARS_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(INSTANCE_EXPLORER_BUILDER_ID) is None:
        register_plot_builder(
            INSTANCE_EXPLORER_BUILDER_ID,
            GlobalInstanceExplorerPlotBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(INSTANCE_EXPLORER_RENDERER_ID) is None:
        register_plot_renderer(
            INSTANCE_EXPLORER_RENDERER_ID,
            GlobalInstanceExplorerPlotRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(INSTANCE_EXPLORER_STYLE_ID) is None:
        register_plot_style(
            INSTANCE_EXPLORER_STYLE_ID,
            metadata={
                "style": INSTANCE_EXPLORER_STYLE_ID,
                "builder_id": INSTANCE_EXPLORER_BUILDER_ID,
                "renderer_id": INSTANCE_EXPLORER_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
    if find_plot_builder_descriptor(INSTANCE_WORKSPACE_BUILDER_ID) is None:
        register_plot_builder(
            INSTANCE_WORKSPACE_BUILDER_ID,
            InstanceWorkspaceDashboardBuilder(),
            source="entrypoint",
        )
    if find_plot_renderer_descriptor(INSTANCE_WORKSPACE_RENDERER_ID) is None:
        register_plot_renderer(
            INSTANCE_WORKSPACE_RENDERER_ID,
            InstanceWorkspaceDashboardRenderer(),
            source="entrypoint",
        )
    if find_plot_style_descriptor(INSTANCE_WORKSPACE_STYLE_ID) is None:
        register_plot_style(
            INSTANCE_WORKSPACE_STYLE_ID,
            metadata={
                "style": INSTANCE_WORKSPACE_STYLE_ID,
                "builder_id": INSTANCE_WORKSPACE_BUILDER_ID,
                "renderer_id": INSTANCE_WORKSPACE_RENDERER_ID,
                "fallbacks": (),
                "legacy_compatible": False,
                "is_default": False,
                "default_for": (),
            },
        )
