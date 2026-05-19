from __future__ import annotations

from functools import wraps
from types import MappingProxyType
from typing import Any

from calibrated_explanations.plugins.plots import PlotRenderContext
from calibrated_explanations.plugins.registry import (
    find_plot_builder_descriptor,
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
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
from .quadrant import (
    BUILDER_ID,
    RENDERER_ID,
    STYLE_ID,
    UncertaintyQuadrantPlotBuilder,
    UncertaintyQuadrantPlotRenderer,
)

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"
class PlotlyVisualizationBootstrap:
    """Bootstrap entry point for Plotly visualization layouts."""

    plugin_meta = {
        "schema_version": 1,
        "name": BOOTSTRAP_ID,
        "version": "0.1.0",
        "provider": "plotly.local",
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
    _install_global_instance_explorer_plot_bridge()
    _install_alternative_feature_summary_plot_bridge()


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
        if key not in {"style", "renderer", "show", "path", "save_ext", "use_legacy", "style_override"}
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

    Some CE versions keep the legacy global renderer as the default unless
    ``use_legacy=False`` is supplied. This bridge preserves the default for all
    normal plots, but makes the explicit Plotly global style work through the
    standard ``explainer.plot(x[, y], style=...)`` API.
    """
    try:
        import calibrated_explanations.plotting as ce_plotting
        from calibrated_explanations.core.calibrated_explainer import CalibratedExplainer
        from calibrated_explanations.core.wrap_explainer import WrapCalibratedExplainer
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if not getattr(ce_plotting.plot_global, "_plotly_instance_explorer_bridge", False):
        original_plot_global = ce_plotting.plot_global

        @wraps(original_plot_global)
        def plot_global_bridge(
            explainer: Any, x: Any, y: Any = None, threshold: Any = None, **kwargs: Any
        ) -> Any:
            if kwargs.get("style") == INSTANCE_EXPLORER_STYLE_ID:
                return _render_global_instance_explorer(explainer, x, y, threshold, kwargs)
            return original_plot_global(explainer, x, y=y, threshold=threshold, **kwargs)

        plot_global_bridge._plotly_instance_explorer_bridge = True  # type: ignore[attr-defined]
        ce_plotting.plot_global = plot_global_bridge

    if not getattr(CalibratedExplainer.plot, "_plotly_instance_explorer_bridge", False):
        original_calibrated_plot = CalibratedExplainer.plot

        @wraps(original_calibrated_plot)
        def calibrated_plot_bridge(
            self: Any, x: Any, y: Any = None, threshold: Any = None, **kwargs: Any
        ) -> Any:
            if kwargs.get("style") != INSTANCE_EXPLORER_STYLE_ID:
                return original_calibrated_plot(self, x, y=y, threshold=threshold, **kwargs)
            style_override = kwargs.pop("style_override", None)
            kwargs["style_override"] = style_override
            from calibrated_explanations.plotting import plot_global

            return plot_global(self, x, y=y, threshold=threshold, **kwargs)

        calibrated_plot_bridge._plotly_instance_explorer_bridge = True  # type: ignore[attr-defined]
        CalibratedExplainer.plot = calibrated_plot_bridge

    if not getattr(WrapCalibratedExplainer.plot, "_plotly_instance_explorer_bridge", False):
        original_wrap_plot = WrapCalibratedExplainer.plot

        @wraps(original_wrap_plot)
        def wrap_plot_bridge(
            self: Any, x: Any, y: Any = None, threshold: Any = None, **kwargs: Any
        ) -> Any:
            if kwargs.get("style") != INSTANCE_EXPLORER_STYLE_ID:
                return original_wrap_plot(self, x, y=y, threshold=threshold, **kwargs)
            assert (
                self._assert_fitted(
                    "The WrapCalibratedExplainer must be fitted and calibrated before plotting."
                )
                ._assert_calibrated(
                    "The WrapCalibratedExplainer must be calibrated before plotting."
                )
                .explainer
                is not None
            )
            cfg = getattr(self, "_cfg", None)
            if cfg is not None:
                if threshold is None:
                    threshold = cfg.threshold
                kwargs.setdefault("low_high_percentiles", cfg.low_high_percentiles)
            kwargs["bins"] = self._get_bins(x, **kwargs)
            return self.explainer.plot(x, y=y, threshold=threshold, **kwargs)

        wrap_plot_bridge._plotly_instance_explorer_bridge = True  # type: ignore[attr-defined]
        WrapCalibratedExplainer.plot = wrap_plot_bridge


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
        intent=MappingProxyType(
            {
                "type": "global",
                "explainer_mode": getattr(explainer, "_last_explanation_mode", None),
            }
        ),
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


register_plotly_visualization_components()
