from __future__ import annotations

import contextlib
from functools import wraps
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

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
from .instance_workspace import (
    _precompute_indices as _dashboard_precompute_indices,
)
from .instance_workspace import (
    _selected_descriptors as _dashboard_selected_descriptors,
)
from .quadrant import (
    BUILDER_ID,
    RENDERER_ID,
    STYLE_ID,
    UncertaintyQuadrantPlotBuilder,
    UncertaintyQuadrantPlotRenderer,
)

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"
_PLOT_BRIDGE_VERSION = 2


class PlotlyVisualizationBootstrap:
    """Bootstrap entry point for Plotly visualization layouts."""

    plugin_meta = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": "0.3.0",
        "provider": "plotly.local",
        "data_modalities": ("tabular",),
        "capabilities": ["plot:bootstrap"],
        "trusted": False,
        "trust": False,
    }


def register_plotly_visualization_components() -> None:
    """Register Plotly visualization builders, renderers, and styles."""
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
    _install_global_instance_explorer_plot_bridge()
    _install_alternative_feature_summary_plot_bridge()
    _install_alternative_bars_plot_bridge()
    _install_factual_bars_plot_bridge()


def _install_factual_bars_plot_bridge() -> None:
    """Route explicit factual styles (bars, simple) through the plugin before CE consumes kwargs.

    FactualExplanation.plot() pops filter_top (positional arg), uncertainty, rnk_metric,
    and rnk_weight before passing remaining kwargs to the plugin dispatcher. This bridge
    intercepts the call first and forwards all parameters intact.
    """
    try:
        from calibrated_explanations.explanations.explanation import FactualExplanation
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if getattr(FactualExplanation.plot, "_factual_bars_bridge", False):
        return

    original_plot = FactualExplanation.plot

    @wraps(original_plot)
    def plot_bridge(self: Any, filter_top: Any = None, **kwargs: Any) -> Any:
        style = kwargs.get("style")
        if style not in (FACTUAL_BARS_STYLE_ID, FACTUAL_SIMPLE_STYLE_ID):
            return original_plot(self, filter_top, **kwargs)
        # filter_top is a positional arg CE would consume before plugin dispatch
        if filter_top is not None:
            kwargs = {**kwargs, "filter_top": filter_top}
        # uncertainty=True → show_uncertainty=True; CE pops uncertainty before dispatch
        if "uncertainty" in kwargs:
            kwargs = {**kwargs, "show_uncertainty": bool(kwargs["uncertainty"])}
        return _render_local_factual_style(self, kwargs, style)

    plot_bridge._factual_bars_bridge = True  # type: ignore[attr-defined]
    FactualExplanation.plot = plot_bridge


_FACTUAL_STYLE_FALLBACKS = {
    FACTUAL_BARS_STYLE_ID: (LocalFactualBarsPlotBuilder, LocalFactualBarsPlotRenderer),
    FACTUAL_SIMPLE_STYLE_ID: (LocalFactualSimplePlotBuilder, LocalFactualSimplePlotRenderer),
}


def _render_local_factual_style(
    explanation: Any, kwargs: dict[str, Any], style_id: str
) -> Any:
    from calibrated_explanations.plugins import (  # noqa: PLC0415
        PlotRenderContext,
        ensure_builtin_plugins,
    )

    ensure_builtin_plugins()

    container = getattr(explanation, "calibrated_explanations", None)
    manager = None
    for candidate in filter(None, [container, getattr(container, "calibrated_explanations", None)]):
        if hasattr(candidate, "plugin_manager"):
            manager = getattr(candidate, "plugin_manager", None)
            break

    resolve_fn = getattr(manager, "resolve_plot_plugin", None)
    if callable(resolve_fn):
        plugin, identifier, _ = resolve_fn(
            explicit_style=style_id,
            renderer_override=kwargs.get("renderer"),
        )
    else:
        builder_cls, renderer_cls = _FACTUAL_STYLE_FALLBACKS[style_id]
        builder_instance = builder_cls()
        renderer_instance = renderer_cls()

        class _DirectPlugin:
            def build(inner_self, ctx: Any) -> Any:  # noqa: N805
                return builder_instance.build(ctx)

            def render(inner_self, artifact: Any, *, context: Any) -> Any:  # noqa: N805
                return renderer_instance.render(artifact, context=context)

        plugin = _DirectPlugin()
        identifier = style_id

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    if path is None and kwargs.get("filename") is not None:
        _fname = Path(str(kwargs["filename"]))
        if _fname.suffix.lower() != ".html":
            _fname = _fname.with_suffix(".html")
        path = str(_fname)
        if "show" not in kwargs:
            show = False
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    _skip_keys = {
        "style", "renderer", "show", "path", "filename",
        "save_ext", "use_legacy", "style_override",
    }
    option_payload = {key: value for key, value in kwargs.items() if key not in _skip_keys}

    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType(
            {"type": "instance", "index": getattr(explanation, "index", None)}
        ),
        style=identifier,
        intent=MappingProxyType({"type": "factual"}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    artifact = plugin.build(context)
    return plugin.render(artifact, context=context)


def _install_alternative_bars_plot_bridge() -> None:
    """Route explicit alternative-bars style through CE's plugin path.

    AlternativeExplanation.plot() drops kwargs before reaching the dispatcher
    in some CE versions. This bridge intercepts calls when style=ALTERNATIVE_BARS_STYLE_ID
    and dispatches directly without altering behavior for any other style.
    """
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False):
        return

    original_plot = AlternativeExplanation.plot

    @wraps(original_plot)
    def plot_bridge(self: Any, filter_top: Any = None, **kwargs: Any) -> Any:
        if kwargs.get("style") != ALTERNATIVE_BARS_STYLE_ID:
            return original_plot(self, filter_top, **kwargs)
        # filter_top is a positional arg in CE's .plot() API; inject it into kwargs
        # so the builder can read it from context.options["filter_top"].
        if filter_top is not None:
            kwargs = {**kwargs, "filter_top": filter_top}
        return _render_local_alternative_bars(self, kwargs)

    plot_bridge._alternative_bars_bridge = True  # type: ignore[attr-defined]
    AlternativeExplanation.plot = plot_bridge


def _render_local_alternative_bars(explanation: Any, kwargs: dict[str, Any]) -> Any:
    from calibrated_explanations.plugins import (  # noqa: PLC0415
        PlotRenderContext,
        ensure_builtin_plugins,
    )

    ensure_builtin_plugins()

    container = getattr(explanation, "calibrated_explanations", None)
    manager = None
    for candidate in filter(None, [container, getattr(container, "calibrated_explanations", None)]):
        if hasattr(candidate, "plugin_manager"):
            manager = getattr(candidate, "plugin_manager", None)
            break

    resolve_fn = getattr(manager, "resolve_plot_plugin", None)
    if callable(resolve_fn):
        plugin, identifier, _ = resolve_fn(
            explicit_style=ALTERNATIVE_BARS_STYLE_ID,
            renderer_override=kwargs.get("renderer"),
        )
    else:
        builder_instance = LocalAlternativeBarsPlotBuilder()
        renderer_instance = LocalAlternativeBarsPlotRenderer()

        class _DirectPlugin:
            def build(inner_self, ctx: Any) -> Any:  # noqa: N805
                return builder_instance.build(ctx)

            def render(inner_self, artifact: Any, *, context: Any) -> Any:  # noqa: N805
                return renderer_instance.render(artifact, context=context)

        plugin = _DirectPlugin()
        identifier = ALTERNATIVE_BARS_STYLE_ID

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    # Translate CE's filename= kwarg to path=, coercing the suffix to .html
    if path is None and kwargs.get("filename") is not None:
        _fname = Path(str(kwargs["filename"]))
        if _fname.suffix.lower() != ".html":
            _fname = _fname.with_suffix(".html")
        path = str(_fname)
        if "show" not in kwargs:
            show = False  # Match CE convention: don't auto-show when saving to file
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    _skip_keys = {
        "style", "renderer", "show", "path", "filename",
        "save_ext", "use_legacy", "style_override",
    }
    option_payload = {key: value for key, value in kwargs.items() if key not in _skip_keys}

    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType(
            {"type": "instance", "index": getattr(explanation, "index", None)}
        ),
        style=identifier,
        intent=MappingProxyType({"type": "alternative"}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    artifact = plugin.build(context)
    return plugin.render(artifact, context=context)


def _install_alternative_feature_summary_plot_bridge() -> None:
    """Route explicit alternative feature summary style through CE's plugin path.

    AlternativeExplanation.plot() ranks features and calls plot_alternative()
    without **kwargs, so the style kwarg is silently dropped before the plugin
    dispatcher is reached. This bridge intercepts the call when the alternative
    feature summary style is explicitly requested and dispatches directly to the
    registered builder and renderer.
    """
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if getattr(AlternativeExplanation.plot, "_alternative_feature_summary_bridge", False):
        return

    original_plot = AlternativeExplanation.plot

    @wraps(original_plot)
    def plot_bridge(self: Any, filter_top: Any = None, **kwargs: Any) -> Any:
        if kwargs.get("style") != ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID:
            return original_plot(self, filter_top, **kwargs)
        return _render_local_alternative_feature_summary(self, kwargs)

    plot_bridge._alternative_feature_summary_bridge = True  # type: ignore[attr-defined]
    AlternativeExplanation.plot = plot_bridge


def _render_local_alternative_feature_summary(
    explanation: Any,
    kwargs: dict[str, Any],
) -> Any:
    from calibrated_explanations.plugins import PlotRenderContext, ensure_builtin_plugins

    ensure_builtin_plugins()

    container = getattr(explanation, "calibrated_explanations", None)
    manager = None
    for candidate in filter(None, [container, getattr(container, "calibrated_explanations", None)]):
        if hasattr(candidate, "plugin_manager"):
            manager = getattr(candidate, "plugin_manager", None)
            break

    resolve_fn = getattr(manager, "resolve_plot_plugin", None)
    if callable(resolve_fn):
        plugin, identifier, _ = resolve_fn(
            explicit_style=ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
            renderer_override=kwargs.get("renderer"),
        )
    else:
        builder_instance = AlternativeFeatureSummaryPlotBuilder()
        renderer_instance = AlternativeFeatureSummaryPlotRenderer()

        class _DirectPlugin:
            def build(inner_self, ctx: Any) -> Any:  # noqa: N805
                return builder_instance.build(ctx)

            def render(inner_self, artifact: Any, *, context: Any) -> Any:  # noqa: N805
                return renderer_instance.render(artifact, context=context)

        plugin = _DirectPlugin()
        identifier = ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    option_payload = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {"style", "renderer", "show", "path", "save_ext", "use_legacy", "style_override"}
    }

    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType(
            {"type": "instance", "index": getattr(explanation, "index", None)}
        ),
        style=identifier,
        intent=MappingProxyType({"type": "alternative"}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    artifact = plugin.build(context)
    return plugin.render(artifact, context=context)


def _install_global_instance_explorer_plot_bridge() -> None:
    """Route explicit global instance-explorer style through CE's plugin path.

    Patches the module attribute ``calibrated_explanations.plotting.plot_global``
    only. ``CalibratedExplainer.plot`` (and ``WrapCalibratedExplainer.plot``,
    which delegates to it with kwargs intact) imports ``plot_global`` from the
    plotting module at call time on CE >= 1.0, so the module-level patch covers
    the whole public ``explainer.plot(x[, y], style=...)`` API without touching
    any CE class or private member.
    """
    try:
        import calibrated_explanations.plotting as ce_plotting
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if getattr(ce_plotting.plot_global, "_plotly_bridge_version", 0) < _PLOT_BRIDGE_VERSION:
        original_plot_global = getattr(
            ce_plotting.plot_global, "__wrapped__", ce_plotting.plot_global
        )

        @wraps(original_plot_global)
        def plot_global_bridge(
            explainer: Any, x: Any, y: Any = None, threshold: Any = None, **kwargs: Any
        ) -> Any:
            if kwargs.get("style") == INSTANCE_EXPLORER_STYLE_ID:
                return _render_global_instance_explorer(explainer, x, y, threshold, kwargs)
            if kwargs.get("style") == INSTANCE_WORKSPACE_STYLE_ID:
                return _render_instance_workspace_dashboard(explainer, x, y, threshold, kwargs)
            return original_plot_global(explainer, x, y=y, threshold=threshold, **kwargs)

        plot_global_bridge._plotly_instance_explorer_bridge = True  # type: ignore[attr-defined]
        plot_global_bridge._plotly_bridge_version = _PLOT_BRIDGE_VERSION  # type: ignore[attr-defined]
        ce_plotting.plot_global = plot_global_bridge


def _render_global_instance_explorer(
    explainer: Any,
    x: Any,
    y: Any,
    threshold: Any,
    kwargs: dict[str, Any],
) -> Any:
    import numpy as np
    from calibrated_explanations.plugins import PlotRenderContext, ensure_builtin_plugins
    from calibrated_explanations.utils.exceptions import ConfigurationError

    show = bool(kwargs.get("show", True))
    bins = kwargs.get("bins")
    path = kwargs.get("path")
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    is_regularized = True
    if "predict_proba" not in dir(explainer.learner) and threshold is None:
        predict, (low, high) = explainer.predict(x, uq_interval=True, bins=bins)
        proba = None
        is_regularized = False
    else:
        proba, (low, high) = explainer.predict_proba(
            x,
            uq_interval=True,
            threshold=threshold,
            bins=bins,
        )
        predict = None
    uncertainty = (
        (np.array(high) - np.array(low)) if (low is not None and high is not None) else None
    )
    payload = {
        "proba": proba,
        "predict": predict,
        "low": low,
        "high": high,
        "uncertainty": uncertainty,
        "y": (list(y) if y is not None else None),
        "is_regularized": is_regularized,
        "threshold": threshold,
        "class_labels": getattr(explainer, "class_labels", None),
        "x": x,
    }

    ensure_builtin_plugins()
    manager = getattr(explainer, "plugin_manager", None)
    resolve_plot_plugin = getattr(manager, "resolve_plot_plugin", None)
    if not callable(resolve_plot_plugin):
        raise ConfigurationError(
            "PluginManager.resolve_plot_plugin is unavailable; cannot resolve plot plugin."
        )
    plugin, identifier, chain = resolve_plot_plugin(
        explicit_style=INSTANCE_EXPLORER_STYLE_ID,
        renderer_override=kwargs.get("renderer"),
    )
    if identifier != INSTANCE_EXPLORER_STYLE_ID:
        raise ConfigurationError(
            "Unable to resolve plot plugin for global explanations; tried: " + ", ".join(chain)
        )

    option_payload = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "style",
            "renderer",
            "show",
            "path",
            "save_ext",
            "use_legacy",
            "bins",
            "style_override",
        }
    }
    option_payload["payload"] = payload
    context = PlotRenderContext(
        explanation=getattr(explainer, "latest_explanation", None),
        instance_metadata=MappingProxyType({"type": "global"}),
        style=identifier,
        intent=MappingProxyType({"type": "global"}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    try:
        artifact = plugin.build(context)
        return plugin.render(artifact, context=context)
    except Exception as exc:
        raise ConfigurationError(
            f"Unable to render plotly.global.instance_explorer; errors: {identifier}: {exc}"
        ) from exc


def _slice_rows(values: Any, indices: list[int]) -> Any:
    if hasattr(values, "iloc"):
        return values.iloc[indices]
    try:
        import numpy as np

        return np.asarray(values)[indices]
    except Exception:
        sequence = list(values)
        return [sequence[index] for index in indices]


def _first_explanation(collection: Any) -> Any:
    explanations = getattr(collection, "explanations", None)
    if explanations is not None:
        return list(explanations)[0]
    try:
        return collection[0]
    except Exception:
        return collection


def _set_original_index(explanation: Any, instance_index: int) -> Any:
    with contextlib.suppress(Exception):
        explanation.index = instance_index
    return explanation


def _workspace_option_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "style",
            "renderer",
            "show",
            "path",
            "save_ext",
            "use_legacy",
            "bins",
            "style_override",
        }
    }


def _global_prediction_payload(
    explainer: Any,
    x: Any,
    y: Any,
    threshold: Any,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np

    bins = kwargs.get("bins")
    is_regularized = True
    if "predict_proba" not in dir(explainer.learner) and threshold is None:
        predict, (low, high) = explainer.predict(x, uq_interval=True, bins=bins)
        proba = None
        is_regularized = False
    else:
        proba, (low, high) = explainer.predict_proba(
            x,
            uq_interval=True,
            threshold=threshold,
            bins=bins,
        )
        predict = None
    uncertainty = (
        (np.array(high) - np.array(low)) if (low is not None and high is not None) else None
    )
    return {
        "proba": proba,
        "predict": predict,
        "low": low,
        "high": high,
        "uncertainty": uncertainty,
        "y": (list(y) if y is not None else None),
        "is_regularized": is_regularized,
        "threshold": threshold,
        "class_labels": getattr(explainer, "class_labels", None),
        "x": x,
    }


def _precompute_workspace_explanations(
    explainer: Any,
    x: Any,
    selected_indices: list[int],
    threshold: Any,
    options: dict[str, Any],
) -> Any:
    factual_explanations = []
    alternative_explanations = []
    include_factual = bool(options.get("include_factual", True))
    include_alternatives = bool(options.get("include_alternatives", True))
    max_rule_size = options.get("max_rule_size")

    for instance_index in selected_indices:
        row = _slice_rows(x, [instance_index])
        if include_factual and callable(getattr(explainer, "explain_factual", None)):
            factual_kwargs = dict(options.get("factual_options", {}) or {})
            if threshold is not None:
                factual_kwargs.setdefault("threshold", threshold)
            factual_explanations.append(
                _set_original_index(
                    _first_explanation(explainer.explain_factual(row, **factual_kwargs)),
                    instance_index,
                )
            )
        if include_alternatives and callable(getattr(explainer, "explore_alternatives", None)):
            alternative_kwargs = dict(options.get("alternative_options", {}) or {})
            if threshold is not None:
                alternative_kwargs.setdefault("threshold", threshold)
            if max_rule_size is not None:
                alternative_kwargs.setdefault("max_rule_size", max_rule_size)
            alternative_explanations.append(
                _set_original_index(
                    _first_explanation(explainer.explore_alternatives(row, **alternative_kwargs)),
                    instance_index,
                )
            )

    first_collection = None
    for explanation in [*factual_explanations, *alternative_explanations]:
        first_collection = getattr(explanation, "calibrated_explanations", None)
        if first_collection is not None:
            break
    return SimpleNamespace(
        explanations=factual_explanations,
        factual_explanations=factual_explanations,
        alternative_explanations=alternative_explanations,
        feature_names=getattr(first_collection, "feature_names", ()),
        batch_metadata=getattr(first_collection, "batch_metadata", {}),
    )


def _render_instance_workspace_dashboard(
    explainer: Any,
    x: Any,
    y: Any,
    threshold: Any,
    kwargs: dict[str, Any],
) -> Any:
    from calibrated_explanations.plugins import PlotRenderContext, ensure_builtin_plugins

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    option_payload = _workspace_option_payload(kwargs)
    global_payload = _global_prediction_payload(explainer, x, y, threshold, kwargs)
    global_options = dict(option_payload.get("global_options", {}) or {})
    global_options.update(
        {
            "payload": global_payload,
            "include_instance_records": True,
            "task": option_payload.get("task", global_options.get("task", "auto")),
            "threshold": threshold,
        }
    )

    preview_context = PlotRenderContext(
        explanation=None,
        instance_metadata=MappingProxyType({"type": "global", "dashboard_mode": "standalone_html"}),
        style=INSTANCE_EXPLORER_STYLE_ID,
        intent=MappingProxyType({"type": "global"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(global_options),
    )
    preview_global_artifact = GlobalInstanceExplorerPlotBuilder().build(preview_context)
    selected_indices, _ = _dashboard_precompute_indices(
        list(preview_global_artifact.get("instance_records", ())),
        option_payload,
    )
    descriptors = _dashboard_selected_descriptors(option_payload)
    precompute_options = dict(option_payload)
    precompute_options["include_factual"] = bool(
        option_payload.get("include_factual", True)
    ) and any("factual_explanation" in set(descriptor.requires) for descriptor in descriptors)
    precompute_options["include_alternatives"] = bool(
        option_payload.get("include_alternatives", True)
    ) and any("alternative_explanation" in set(descriptor.requires) for descriptor in descriptors)
    local_payload = _precompute_workspace_explanations(
        explainer,
        x,
        selected_indices,
        threshold,
        precompute_options,
    )

    option_payload["global_options"] = global_options
    ensure_builtin_plugins()
    context = PlotRenderContext(
        explanation=local_payload,
        instance_metadata=MappingProxyType({"type": "dashboard"}),
        style=INSTANCE_WORKSPACE_STYLE_ID,
        intent=MappingProxyType({"type": "dashboard"}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    artifact = InstanceWorkspaceDashboardBuilder().build(context)
    return InstanceWorkspaceDashboardRenderer().render(artifact, context=context)


register_plotly_visualization_components()
