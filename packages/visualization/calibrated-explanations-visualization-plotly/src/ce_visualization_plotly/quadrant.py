from __future__ import annotations

import logging
import warnings
from collections.abc import Mapping
from math import ceil
from pathlib import Path
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)

STYLE_ID = "plotly.local.uncertainty_quadrant"
BUILDER_ID = "official.visualization.plotly.local.uncertainty_quadrant.builder"
RENDERER_ID = "official.visualization.plotly.local.uncertainty_quadrant.renderer"

_LOGGER = logging.getLogger(__name__)
_QUADRANT_COLORS = {
    "robust_driver": "#1b9e77",
    "uncertain_driver": "#d95f02",
    "stable_minor": "#7570b3",
    "weak_or_noisy": "#666666",
}
_DIRECTION_SYMBOLS = {
    "positive": "circle",
    "negative": "diamond",
    "crosses_zero": "x",
}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[midpoint])
    return float((sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2.0)


def _quantile_75(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, ceil(0.75 * len(sorted_values)) - 1)
    return float(sorted_values[index])


def _is_degenerate_threshold(threshold: float, values: list[float]) -> bool:
    unique_values = {float(value) for value in values}
    return threshold <= 0.0 or len(unique_values) <= 1


def _resolve_threshold(
    *,
    name: str,
    values: list[float],
    explicit_value: Any,
    strategy: str,
) -> tuple[float, str]:
    explicit = _as_float(explicit_value)
    if strategy == "explicit":
        if explicit is None:
            raise ValueError(f"{name}_threshold is required when threshold_strategy='explicit'.")
        threshold = explicit
        source = "explicit"
    elif strategy == "quantile_75":
        threshold = _quantile_75(values)
        source = "quantile_75"
    elif strategy == "median":
        threshold = explicit if explicit is not None else _median(values)
        source = "option" if explicit is not None else "median"
    else:
        raise ValueError("threshold_strategy must be one of median, quantile_75, or explicit.")

    if _is_degenerate_threshold(threshold, values):
        fallback = _quantile_75(values)
        if fallback != threshold:
            return fallback, f"{source}:degenerate_fallback_quantile_75"
        return fallback, f"{source}:degenerate"
    return threshold, source


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


def _direction_for(contribution: float, crosses_zero: bool) -> str:
    if crosses_zero:
        return "crosses_zero"
    if contribution >= 0.0:
        return "positive"
    return "negative"


def _quadrant_for(
    *,
    absolute_impact: float,
    interval_width: float,
    impact_threshold: float,
    uncertainty_threshold: float,
) -> str:
    high_impact = absolute_impact >= impact_threshold
    low_uncertainty = interval_width <= uncertainty_threshold
    if high_impact and low_uncertainty:
        return "robust_driver"
    if high_impact:
        return "uncertain_driver"
    if low_uncertainty:
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
    get_rules = getattr(local_explanation, "get_rules", None)
    rules = get_rules() if callable(get_rules) else getattr(local_explanation, "rules", None)
    if not isinstance(rules, Mapping):
        build_payload = getattr(local_explanation, "build_rules_payload", None)
        if callable(build_payload):
            payload = build_payload()
            rules = payload if isinstance(payload, Mapping) else getattr(payload, "rules", None)
    if not isinstance(rules, Mapping):
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
    skipped_rules = 0

    for index, raw_weight in enumerate(weights):
        contribution = _as_float(raw_weight)
        low = _as_float(_sequence_get(lows, index))
        high = _as_float(_sequence_get(highs, index))
        if contribution is None or low is None or high is None:
            skipped_rules += 1
            continue
        feature = _sequence_get(features, index)
        feature_value = _sequence_get(feature_values, index, _sequence_get(values, index))
        width = high - low
        items.append(
            {
                "index": index,
                "feature_index": feature,
                "rule": str(_sequence_get(labels, index, f"rule {index}")),
                "feature_name": _feature_name(collection, feature),
                "instance_value": feature_value,
                "contribution": contribution,
                "absolute_impact": abs(contribution),
                "low": low,
                "high": high,
                "interval_width": width,
            }
        )
    if skipped_rules:
        _warn_fallback(
            f"omitted {skipped_rules} rule(s) without a weight and two-sided "
            "weight interval; the quadrant requires weight, weight_low, and "
            "weight_high per rule."
        )
    return items


def _apply_sort(items: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by in {"input", "none", ""}:
        return list(items)
    if sort_by in {"absolute_impact", "abs_contribution", "impact", "effect"}:
        return sorted(items, key=lambda item: (-item["absolute_impact"], item["index"]))
    if sort_by in {"uncertainty", "width"}:
        return sorted(items, key=lambda item: (-item["interval_width"], item["index"]))
    if sort_by == "contribution":
        return sorted(items, key=lambda item: (item["contribution"], item["index"]))
    if sort_by == "quadrant":
        return sorted(items, key=lambda item: (item.get("quadrant", ""), item["index"]))
    raise ValueError(
        "sort_by must be one of input, absolute_impact, impact, uncertainty, "
        "width, contribution, or quadrant."
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
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "intent": "factual",
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

        threshold_strategy = str(options.get("threshold_strategy", "median"))
        impact_values = [item["absolute_impact"] for item in items]
        uncertainty_values = [item["interval_width"] for item in items]
        impact_threshold, impact_source = _resolve_threshold(
            name="impact",
            values=impact_values,
            explicit_value=options.get("impact_threshold"),
            strategy=threshold_strategy,
        )
        uncertainty_threshold, uncertainty_source = _resolve_threshold(
            name="uncertainty",
            values=uncertainty_values,
            explicit_value=options.get("uncertainty_threshold"),
            strategy=threshold_strategy,
        )

        for item in items:
            crosses_zero = item["low"] <= 0.0 <= item["high"]
            item["crosses_zero"] = crosses_zero
            item["direction"] = _direction_for(item["contribution"], crosses_zero)
            item["quadrant"] = _quadrant_for(
                absolute_impact=item["absolute_impact"],
                interval_width=item["interval_width"],
                impact_threshold=impact_threshold,
                uncertainty_threshold=uncertainty_threshold,
            )
            item["status_flags"] = ("sign_uncertain",) if crosses_zero else ()

        sorted_items = _apply_sort(items, str(options.get("sort_by", "absolute_impact")))
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
                "impact": impact_threshold,
                "uncertainty": uncertainty_threshold,
                "impact_source": impact_source,
                "uncertainty_source": uncertainty_source,
                "strategy": threshold_strategy,
            },
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "metadata": {
                "instance_index": getattr(local_explanation, "index", instance_index),
                "mode": mode_metadata,
                "task": mode_metadata.get("task"),
                "sort_by": str(options.get("sort_by", "absolute_impact")),
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
        "data_modalities": ("tabular",),
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
                "Install plotly (a mandatory dependency of "
                "calibrated-explanations-visualization-plotly); your "
                "environment appears to be missing or shadowing it."
            ) from exc

        items = list(artifact.get("items", ()))
        x_values = [item["absolute_impact"] for item in items]
        y_values = [item["interval_width"] for item in items]
        customdata = [
            [
                item.get("rule"),
                item.get("feature_name"),
                item.get("instance_value"),
                item.get("contribution"),
                item.get("absolute_impact"),
                item.get("low"),
                item.get("high"),
                item.get("interval_width"),
                item.get("direction"),
                item.get("quadrant"),
                item.get("crosses_zero"),
            ]
            for item in items
        ]
        colors = [_QUADRANT_COLORS.get(item.get("quadrant"), "#666666") for item in items]
        symbols = [_DIRECTION_SYMBOLS.get(item.get("direction"), "circle") for item in items]
        thresholds = dict(artifact.get("thresholds", {}) or {})
        impact_threshold = float(thresholds.get("impact", 0.0))
        uncertainty_threshold = float(thresholds.get("uncertainty", 0.0))

        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers",
                marker={
                    "size": 11,
                    "color": colors,
                    "symbol": symbols,
                    "line": {"color": "white", "width": 1},
                },
                customdata=customdata,
                hovertemplate=(
                    "rule: %{customdata[0]}<br>"
                    "feature: %{customdata[1]}<br>"
                    "value: %{customdata[2]}<br>"
                    "signed contribution: %{customdata[3]:.6g}<br>"
                    "absolute impact: %{customdata[4]:.6g}<br>"
                    "low: %{customdata[5]:.6g}<br>"
                    "high: %{customdata[6]:.6g}<br>"
                    "interval width: %{customdata[7]:.6g}<br>"
                    "direction: %{customdata[8]}<br>"
                    "quadrant: %{customdata[9]}<br>"
                    "crosses zero: %{customdata[10]}<extra></extra>"
                ),
                name="rules",
            )
        )
        figure.add_vline(
            x=impact_threshold,
            line_width=1,
            line_dash="dash",
            line_color="#444444",
        )
        figure.add_hline(
            y=uncertainty_threshold,
            line_width=1,
            line_dash="dash",
            line_color="#444444",
        )
        x_max = max([impact_threshold, *x_values, 1.0])
        y_max = max([uncertainty_threshold, *y_values, 1.0])
        low_x = impact_threshold / 2.0 if impact_threshold > 0 else x_max * 0.25
        high_x = impact_threshold + max(x_max - impact_threshold, x_max * 0.25) / 2.0
        low_y = uncertainty_threshold / 2.0 if uncertainty_threshold > 0 else y_max * 0.25
        high_y = uncertainty_threshold + max(y_max - uncertainty_threshold, y_max * 0.25) / 2.0
        for x_pos, y_pos, label in (
            (high_x, low_y, "high impact / low uncertainty"),
            (high_x, high_y, "high impact / high uncertainty"),
            (low_x, low_y, "low impact / low uncertainty"),
            (low_x, high_y, "low impact / high uncertainty"),
        ):
            figure.add_annotation(
                x=x_pos,
                y=y_pos,
                text=label,
                showarrow=False,
                font={"size": 11, "color": "#555555"},
                bgcolor="rgba(255,255,255,0.72)",
                bordercolor="rgba(0,0,0,0.12)",
                borderwidth=1,
            )
        figure.update_layout(
            template="plotly_white",
            title="Local uncertainty quadrant",
            xaxis_title="Absolute local impact",
            yaxis_title="Calibrated uncertainty width",
            legend_title_text="Quadrant",
            margin={"l": 5, "r": 24, "t": 48, "b": 48},
            autosize=True,
        )
        if hasattr(figure, "update_xaxes"):
            figure.update_xaxes(automargin=True)
        if hasattr(figure, "update_yaxes"):
            figure.update_yaxes(automargin=True)

        saved_paths: tuple[str, ...] = ()
        if context.path:
            html_path = Path(context.path)
            if html_path.suffix.lower() != ".html":
                html_path = html_path.with_suffix(".html")
            figure.write_html(
                str(html_path),
                config={"responsive": True, "displayModeBar": "hover"},
            )
            saved_paths = (str(html_path),)
        if context.show:
            figure.show()

        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={"figure": figure},
        )
