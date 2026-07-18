"""Compatibility bridges around CE's public plot dispatch.

Why this module exists
----------------------
CE 1.0.x consumes several kwargs *before* custom plot styles are dispatched:

* ``FactualExplanation.plot`` / ``AlternativeExplanation.plot`` pop
  ``filter_top`` (a positional argument), ``uncertainty``, ``rnk_metric``,
  ``rnk_weight``, ``filename`` and ``show`` before calling the plugin
  dispatcher, and ``AlternativeExplanation.plot`` calls ``plot_alternative``
  without forwarding ``**kwargs`` at all, silently dropping ``style``.
* ``calibrated_explanations.plotting.plot_global`` has no dispatch path for
  third-party global or dashboard styles.

To make ``explanation.plot(style="plotly.…")`` and
``explainer.plot(x, style="plotly.…")`` work with full option fidelity, this
module wraps — at registration time — the two public ``.plot`` methods and the
public ``plotting.plot_global`` module attribute. This is deliberate
monkey-patching of public CE symbols, not ordinary entry-point registration,
and is treated as a compatibility bridge:

* every wrapper is guarded by a marker attribute, so installation is
  idempotent and independent of import order;
* ``functools.wraps`` preserves the wrapped function's metadata (and
  propagates the marker attributes through chained wrappers);
* non-Plotly styles fall straight through to the original callable;
* no CE-private members are touched.

Needed for: calibrated-explanations >= 1.0.0rc1, < 2 (all currently released
1.0.x versions).

Removal condition
-----------------
Delete this module (and the ``install_ce_plot_bridges()`` call in
``plugin.py``) once CE's explanation-level ``plot()`` forwards all kwargs —
including ``filter_top``/``uncertainty``/``rnk_metric``/``rnk_weight`` — to
the plugin dispatcher and ``plot_global`` resolves third-party global styles
through the registry. Re-test ``tests/test_package_contract.py`` and the
bridge boundary tests when raising the CE floor.
"""

from __future__ import annotations

import contextlib
from functools import wraps
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

from .alternative_bars import (
    STYLE_ID as ALTERNATIVE_BARS_STYLE_ID,
)
from .alternative_bars import (
    LocalAlternativeBarsPlotBuilder,
    LocalAlternativeBarsPlotRenderer,
)
from .alternative_feature_summary import (
    STYLE_ID as ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
)
from .alternative_feature_summary import (
    AlternativeFeatureSummaryPlotBuilder,
    AlternativeFeatureSummaryPlotRenderer,
)
from .factual_bars import (
    STYLE_ID as FACTUAL_BARS_STYLE_ID,
)
from .factual_bars import (
    LocalFactualBarsPlotBuilder,
    LocalFactualBarsPlotRenderer,
)
from .factual_simple import (
    STYLE_ID as FACTUAL_SIMPLE_STYLE_ID,
)
from .factual_simple import (
    LocalFactualSimplePlotBuilder,
    LocalFactualSimplePlotRenderer,
)
from .instance_explorer import (
    STYLE_ID as INSTANCE_EXPLORER_STYLE_ID,
)
from .instance_explorer import (
    GlobalInstanceExplorerPlotBuilder,
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

_PLOT_BRIDGE_VERSION = 2

# Local styles dispatched through the explanation-level bridges, with the
# direct builder/renderer pair used when no plugin manager is reachable.
_FACTUAL_STYLE_FALLBACKS = {
    FACTUAL_BARS_STYLE_ID: (LocalFactualBarsPlotBuilder, LocalFactualBarsPlotRenderer),
    FACTUAL_SIMPLE_STYLE_ID: (LocalFactualSimplePlotBuilder, LocalFactualSimplePlotRenderer),
}
_ALTERNATIVE_STYLE_FALLBACKS = {
    ALTERNATIVE_BARS_STYLE_ID: (
        LocalAlternativeBarsPlotBuilder,
        LocalAlternativeBarsPlotRenderer,
    ),
    ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID: (
        AlternativeFeatureSummaryPlotBuilder,
        AlternativeFeatureSummaryPlotRenderer,
    ),
}

_SKIP_OPTION_KEYS = {
    "style",
    "renderer",
    "show",
    "path",
    "filename",
    "save_ext",
    "use_legacy",
    "style_override",
}


def install_ce_plot_bridges() -> None:
    """Install all CE plot-dispatch bridges (idempotent)."""
    _install_plot_global_bridge()
    _install_alternative_plot_bridge()
    _install_factual_plot_bridge()


# ---------------------------------------------------------------------------
# Explanation-level bridges (FactualExplanation.plot / AlternativeExplanation.plot)
# ---------------------------------------------------------------------------


def _install_factual_plot_bridge() -> None:
    """Route explicit factual styles (bars, simple) through the plugin before CE consumes kwargs."""
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
        if style not in _FACTUAL_STYLE_FALLBACKS:
            return original_plot(self, filter_top, **kwargs)
        # filter_top is a positional arg CE would consume before plugin dispatch
        if filter_top is not None:
            kwargs = {**kwargs, "filter_top": filter_top}
        # uncertainty=True → show_uncertainty=True; CE pops uncertainty before dispatch
        if "uncertainty" in kwargs:
            kwargs = {**kwargs, "show_uncertainty": bool(kwargs["uncertainty"])}
        return _render_local_style(
            self, kwargs, style, intent_type="factual", fallbacks=_FACTUAL_STYLE_FALLBACKS
        )

    plot_bridge._factual_bars_bridge = True  # type: ignore[attr-defined]
    FactualExplanation.plot = plot_bridge


def _install_alternative_plot_bridge() -> None:
    """Route explicit alternative styles (bars, feature summary) through the plugin.

    ``AlternativeExplanation.plot()`` ranks features and calls
    ``plot_alternative()`` without ``**kwargs``, so the ``style`` kwarg is
    silently dropped before the plugin dispatcher is reached.
    """
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation
    except Exception:  # pragma: no cover - depends on installed CE version
        return

    if getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False) and getattr(
        AlternativeExplanation.plot, "_alternative_feature_summary_bridge", False
    ):
        return

    original_plot = AlternativeExplanation.plot

    @wraps(original_plot)
    def plot_bridge(self: Any, filter_top: Any = None, **kwargs: Any) -> Any:
        style = kwargs.get("style")
        if style not in _ALTERNATIVE_STYLE_FALLBACKS:
            return original_plot(self, filter_top, **kwargs)
        # filter_top is a positional arg in CE's .plot() API; inject it into kwargs
        # so the builder can read it from context.options["filter_top"].
        if filter_top is not None:
            kwargs = {**kwargs, "filter_top": filter_top}
        return _render_local_style(
            self, kwargs, style, intent_type="alternative", fallbacks=_ALTERNATIVE_STYLE_FALLBACKS
        )

    # Both legacy marker names are kept so existing idempotence checks (and any
    # older wrapper still on the class in-process) remain valid.
    plot_bridge._alternative_bars_bridge = True  # type: ignore[attr-defined]
    plot_bridge._alternative_feature_summary_bridge = True  # type: ignore[attr-defined]
    AlternativeExplanation.plot = plot_bridge


def _render_local_style(
    explanation: Any,
    kwargs: dict[str, Any],
    style_id: str,
    *,
    intent_type: str,
    fallbacks: dict[str, tuple[type, type]],
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
        builder_cls, renderer_cls = fallbacks[style_id]
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

    option_payload = {
        key: value for key, value in kwargs.items() if key not in _SKIP_OPTION_KEYS
    }

    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType(
            {"type": "instance", "index": getattr(explanation, "index", None)}
        ),
        style=identifier,
        intent=MappingProxyType({"type": intent_type}),
        show=show,
        path=path,
        save_ext=save_ext_value,
        options=MappingProxyType(option_payload),
    )
    artifact = plugin.build(context)
    return plugin.render(artifact, context=context)


# ---------------------------------------------------------------------------
# Module-level bridge (plotting.plot_global)
# ---------------------------------------------------------------------------


def _install_plot_global_bridge() -> None:
    """Route explicit global/dashboard styles through CE's plugin path.

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


def _global_option_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    skip = (_SKIP_OPTION_KEYS - {"filename"}) | {"bins"}
    return {key: value for key, value in kwargs.items() if key not in skip}


def _global_prediction_payload(
    explainer: Any,
    x: Any,
    y: Any,
    threshold: Any,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

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


def _render_global_instance_explorer(
    explainer: Any,
    x: Any,
    y: Any,
    threshold: Any,
    kwargs: dict[str, Any],
) -> Any:
    from calibrated_explanations.plugins import (  # noqa: PLC0415
        PlotRenderContext,
        ensure_builtin_plugins,
    )
    from calibrated_explanations.utils.exceptions import ConfigurationError  # noqa: PLC0415

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    payload = _global_prediction_payload(explainer, x, y, threshold, kwargs)

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

    option_payload = _global_option_payload(kwargs)
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


# ---------------------------------------------------------------------------
# Dashboard dispatch helpers
# ---------------------------------------------------------------------------


def _slice_rows(values: Any, indices: list[int]) -> Any:
    if hasattr(values, "iloc"):
        return values.iloc[indices]
    try:
        import numpy as np  # noqa: PLC0415

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
    from calibrated_explanations.plugins import (  # noqa: PLC0415
        PlotRenderContext,
        ensure_builtin_plugins,
    )

    show = bool(kwargs.get("show", True))
    path = kwargs.get("path")
    save_ext_value = kwargs.get("save_ext")
    if isinstance(save_ext_value, (list, tuple)):
        save_ext_value = tuple(save_ext_value)

    option_payload = _global_option_payload(kwargs)
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


__all__ = ["install_ce_plot_bridges"]
