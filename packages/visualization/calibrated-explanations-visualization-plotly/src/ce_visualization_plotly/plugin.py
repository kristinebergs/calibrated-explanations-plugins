from __future__ import annotations

import logging
import statistics
import warnings
from pathlib import Path
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
    find_plot_renderer_descriptor,
    find_plot_style_descriptor,
    register_plot_builder,
    register_plot_renderer,
    register_plot_style,
)

STYLE_ID = "plotly.local.uncertainty_quadrant"
BUILDER_ID = "plotly.local.uncertainty_quadrant.builder"
RENDERER_ID = "plotly.local.uncertainty_quadrant.renderer"
BOOTSTRAP_ID = "plotly.local.uncertainty_quadrant.bootstrap"

_LOGGER = logging.getLogger(__name__)
_STATUS_COLORS = {
    "robust_driver": "#1b9e77",
    "large_uncertain": "#d95f02",
    "stable_minor": "#7570b3",
    "weak_or_noisy": "#666666",
    "sign_uncertain": "#e7298a",
}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _sequence_get(values: Any, index: int, default: Any = None) -> Any:
    if values is None:
        return default
    try:
        return values[index]
    except (IndexError, KeyError, TypeError):
        return default


def _collection_for(explanation: Any) -> Any:
    return getattr(explanation, "calibrated_explanations", explanation)


def _select_local_explanation(explanation: Any, instance_index: int | None) -> Any:
    explanations = getattr(explanation, "explanations", None)
    if explanations is None:
        return explanation
    if len(explanations) == 0:
        raise ValueError("No explanations are available for plotting.")
    selected = 0 if instance_index is None else int(instance_index)
    return explanations[selected]


def _feature_name(collection: Any, feature: Any) -> str | None:
    names = getattr(collection, "feature_names", None)
    if callable(names):
        names = names()
    index = _as_float(feature)
    if names is not None and index is not None and index.is_integer():
        name = _sequence_get(names, int(index))
        if name is not None:
            return str(name)
    if feature is None:
        return None
    return str(feature)


def _status_for(
    *,
    contribution: float,
    low: float,
    high: float,
    width: float,
    effect_threshold: float,
    width_threshold: float,
) -> str:
    if low <= 0.0 <= high:
        return "sign_uncertain"
    large_effect = abs(contribution) >= effect_threshold
    narrow = width <= width_threshold
    if large_effect and narrow:
        return "robust_driver"
    if large_effect:
        return "large_uncertain"
    if narrow:
        return "stable_minor"
    return "weak_or_noisy"


def _prediction_header(local_explanation: Any) -> dict[str, Any]:
    prediction = getattr(local_explanation, "prediction", None)
    if isinstance(prediction, dict):
        return {
            "prediction": prediction.get("predict"),
            "low": prediction.get("low"),
            "high": prediction.get("high"),
            "classes": prediction.get("classes"),
        }
    return {}


def _mode_metadata(explanation: Any, local_explanation: Any) -> dict[str, Any]:
    collection = _collection_for(local_explanation)
    batch_metadata = dict(getattr(explanation, "batch_metadata", {}) or {})
    task = batch_metadata.get("task")
    get_mode = getattr(local_explanation, "get_mode", None)
    mode = get_mode() if callable(get_mode) else batch_metadata.get("mode")
    feature_names = getattr(collection, "feature_names", ())
    if callable(feature_names):
        feature_names = feature_names()
    return {
        "task": task,
        "mode": mode,
        "is_regression": bool(getattr(local_explanation, "is_regression", lambda: False)()),
        "is_probabilistic": bool(getattr(local_explanation, "is_probabilistic", lambda: False)()),
        "feature_names": tuple(feature_names or ()),
    }


def _extract_rule_items(local_explanation: Any) -> list[dict[str, Any]]:
    rules = getattr(local_explanation, "rules", None)
    if not isinstance(rules, dict):
        build_payload = getattr(local_explanation, "build_rules_payload", None)
        if callable(build_payload):
            payload = build_payload()
            rules = payload if isinstance(payload, dict) else getattr(payload, "rules", None)
    if not isinstance(rules, dict):
        raise ValueError("The explanation does not expose factual rule contributions.")

    weights = list(rules.get("weight", ()))
    lows = list(rules.get("weight_low", ()))
    highs = list(rules.get("weight_high", ()))
    labels = list(rules.get("rule", ()))
    features = list(rules.get("feature", ()))
    values = list(rules.get("value", ()))
    feature_values = list(rules.get("feature_value", ()))
    collection = _collection_for(local_explanation)
    items: list[dict[str, Any]] = []

    for index, raw_weight in enumerate(weights):
        contribution = _as_float(raw_weight)
        low = _as_float(_sequence_get(lows, index))
        high = _as_float(_sequence_get(highs, index))
        if contribution is None or low is None or high is None:
            continue
        feature = _sequence_get(features, index)
        feature_value = _sequence_get(feature_values, index, _sequence_get(values, index))
        width = high - low
        items.append(
            {
                "index": index,
                "rule_label": str(_sequence_get(labels, index, f"rule {index}")),
                "feature": feature,
                "feature_name": _feature_name(collection, feature),
                "instance_value": feature_value,
                "contribution": contribution,
                "low": low,
                "high": high,
                "interval_width": width,
            }
        )
    return items


def _apply_sort(items: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by in {"input", "none", ""}:
        return list(items)
    if sort_by in {"abs_contribution", "effect"}:
        return sorted(items, key=lambda item: (-abs(item["contribution"]), item["index"]))
    if sort_by == "width":
        return sorted(items, key=lambda item: (-item["interval_width"], item["index"]))
    if sort_by == "contribution":
        return sorted(items, key=lambda item: (item["contribution"], item["index"]))
    if sort_by == "status":
        return sorted(items, key=lambda item: (item.get("status_label", ""), item["index"]))
    raise ValueError(
        "sort_by must be one of input, abs_contribution, effect, width, contribution, or status."
    )


def _warn_fallback(reason: str) -> None:
    message = f"Plotly uncertainty quadrant fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


class UncertaintyQuadrantPlotBuilder(PlotBuilder):
    """Build a private Plotly uncertainty-quadrant artifact for one factual explanation."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": "0.1.0",
        "provider": "plotly.local",
        "style": STYLE_ID,
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        intent_type = context.intent.get("type")
        if intent_type not in (None, "factual"):
            raise ValueError(
                "plotly.local.uncertainty_quadrant supports factual local explanations only."
            )

        options = dict(context.options)
        instance_index = options.get("instance_index")
        local_explanation = _select_local_explanation(context.explanation, instance_index)
        is_alternative = getattr(local_explanation, "is_alternative", False)
        if bool(is_alternative() if callable(is_alternative) else is_alternative):
            raise ValueError(
                "plotly.local.uncertainty_quadrant does not support alternative explanations."
            )

        items = _extract_rule_items(local_explanation)
        if not items:
            raise ValueError("No factual rule contributions were available for plotting.")

        effect_threshold = _as_float(options.get("effect_threshold"))
        if effect_threshold is None:
            effect_threshold = _median([abs(item["contribution"]) for item in items])
        width_threshold = _as_float(options.get("width_threshold"))
        if width_threshold is None:
            width_threshold = _median([item["interval_width"] for item in items])

        for item in items:
            item["status_label"] = _status_for(
                contribution=item["contribution"],
                low=item["low"],
                high=item["high"],
                width=item["interval_width"],
                effect_threshold=effect_threshold,
                width_threshold=width_threshold,
            )

        sorted_items = _apply_sort(items, str(options.get("sort_by", "abs_contribution")))
        filter_top = options.get("filter_top")
        if filter_top is not None:
            sorted_items = sorted_items[: int(filter_top)]

        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        return {
            "artifact_type": STYLE_ID,
            "style": STYLE_ID,
            "prediction": _prediction_header(local_explanation),
            "items": sorted_items,
            "thresholds": {
                "effect": effect_threshold,
                "width": width_threshold,
                "effect_source": (
                    "option" if "effect_threshold" in options else "median_abs_contribution"
                ),
                "width_source": (
                    "option" if "width_threshold" in options else "median_interval_width"
                ),
                "show_width_reference": bool(options.get("show_width_reference", True)),
            },
            "metadata": {
                "instance_index": getattr(local_explanation, "index", instance_index),
                "mode": mode_metadata,
                "task": mode_metadata.get("task"),
                "sort_by": str(options.get("sort_by", "abs_contribution")),
                "filter_top": filter_top,
            },
        }


class UncertaintyQuadrantPlotRenderer(PlotRenderer):
    """Render uncertainty-quadrant artifacts as Plotly figures."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": "0.1.0",
        "provider": "plotly.local",
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": ("plotly",),
        "trusted": False,
        "trust": False,
        "supports_interactive": True,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        if artifact.get("artifact_type") != STYLE_ID:
            _warn_fallback("received an unexpected artifact type; rendering with available fields.")
        try:
            import plotly.graph_objects as go
        except ImportError as exc:
            raise RuntimeError(
                "Plotly is required to render plotly.local.uncertainty_quadrant. "
                "Install this package with the [plotly] extra."
            ) from exc

        items = list(artifact.get("items", ()))
        x_values = [item["contribution"] for item in items]
        y_values = [item["interval_width"] for item in items]
        customdata = [
            [
                item.get("rule_label"),
                item.get("feature_name"),
                item.get("instance_value"),
                item.get("contribution"),
                item.get("low"),
                item.get("high"),
                item.get("interval_width"),
                item.get("status_label"),
            ]
            for item in items
        ]
        colors = [_STATUS_COLORS.get(item.get("status_label"), "#666666") for item in items]

        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers",
                marker={"size": 11, "color": colors, "line": {"color": "white", "width": 1}},
                customdata=customdata,
                hovertemplate=(
                    "rule: %{customdata[0]}<br>"
                    "feature: %{customdata[1]}<br>"
                    "value: %{customdata[2]}<br>"
                    "contribution: %{customdata[3]:.6g}<br>"
                    "low: %{customdata[4]:.6g}<br>"
                    "high: %{customdata[5]:.6g}<br>"
                    "interval width: %{customdata[6]:.6g}<br>"
                    "status: %{customdata[7]}<extra></extra>"
                ),
                name="rules",
            )
        )
        figure.add_vline(x=0, line_width=1, line_dash="dash", line_color="#444444")
        thresholds = dict(artifact.get("thresholds", {}) or {})
        if thresholds.get("show_width_reference", True):
            figure.add_hline(
                y=float(thresholds.get("width", 0.0)),
                line_width=1,
                line_dash="dot",
                line_color="#888888",
            )
        figure.update_layout(
            template="plotly_white",
            title="Local uncertainty quadrant",
            xaxis_title="Signed contribution",
            yaxis_title="Contribution interval width",
            legend_title_text="Status",
            margin={"l": 60, "r": 24, "t": 56, "b": 56},
        )

        saved_paths: tuple[str, ...] = ()
        if context.path:
            html_path = Path(context.path)
            if html_path.suffix.lower() != ".html":
                html_path = html_path.with_suffix(".html")
            figure.write_html(str(html_path))
            saved_paths = (str(html_path),)
        if context.show:
            figure.show()

        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={"figure": figure},
        )


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
    """Register Plotly uncertainty-quadrant builder, renderer, and style."""
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


register_plotly_visualization_components()
