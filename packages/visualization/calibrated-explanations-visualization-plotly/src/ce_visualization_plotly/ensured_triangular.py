from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)
from calibrated_explanations.utils.helper import calculate_metrics
from calibrated_explanations.viz.builders import build_triangular_plotspec

STYLE_ID = "plotly.local.ensured_triangular"
BUILDER_ID = "official.visualization.plotly.local.ensured_triangular.builder"
RENDERER_ID = "official.visualization.plotly.local.ensured_triangular.renderer"

_LOGGER = logging.getLogger(__name__)
_ORIGINAL_POINT_ID = "original-point"
_RULE_FALLBACK = "Rule condition unavailable"
_ORIGINAL_COLOR = "#d62728"
_RULE_COLOR = "#1f77b4"
_ARROW_COLOR = "rgba(110, 110, 110, 0.75)"


def _warn_fallback(reason: str) -> None:
    message = f"Plotly ensured triangular fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sequence_get(values: Any, index: int, default: Any = None) -> Any:
    if values is None:
        return default
    try:
        return values[index]
    except (IndexError, KeyError, TypeError):
        return default


def _serialise_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_serialise_value(item) for item in value]
    return value


def _display_value(value: Any) -> str:
    serialised = _serialise_value(value)
    if isinstance(serialised, list):
        return ", ".join(str(item) for item in serialised)
    return str(serialised)


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


def _is_alternative_explanation(local_explanation: Any) -> bool:
    sentinel = object()
    is_alternative = getattr(local_explanation, "is_alternative", sentinel)
    if callable(is_alternative):
        return bool(is_alternative())
    if isinstance(is_alternative, bool):
        return is_alternative
    class_name = type(local_explanation).__name__.lower()
    if "alternative" in class_name:
        return True
    get_rules = getattr(local_explanation, "get_rules", None)
    return callable(get_rules) and hasattr(local_explanation, "prediction")


def _feature_name(collection: Any, feature: Any) -> str | None:
    names = getattr(collection, "feature_names", None)
    if callable(names):
        names = names()
    index = _as_float(feature)
    if names is not None and index is not None and index.is_integer():
        try:
            return str(names[int(index)])
        except (IndexError, TypeError):
            return None
    if feature is None:
        return None
    return str(feature)


def _mode_metadata(explanation: Any, local_explanation: Any) -> dict[str, Any]:
    batch_metadata = dict(getattr(explanation, "batch_metadata", {}) or {})
    get_mode = getattr(local_explanation, "get_mode", None)
    raw_mode = get_mode() if callable(get_mode) else batch_metadata.get("mode")
    is_regression = bool(getattr(local_explanation, "is_regression", lambda: False)())
    is_probabilistic = bool(getattr(local_explanation, "is_probabilistic", lambda: False)())
    task = batch_metadata.get("task")
    if task is None:
        task = "regression" if is_regression else "classification" if is_probabilistic else raw_mode
    mode = raw_mode or task
    return {
        "task": task,
        "mode": mode,
        "is_regression": is_regression,
        "is_probabilistic": is_probabilistic,
    }


def _resolve_alternative_rules(local_explanation: Any) -> dict[str, Any]:
    if getattr(local_explanation, "has_conjunctive_rules", False) and getattr(
        local_explanation, "conjunctive_rules", None
    ):
        rules = local_explanation.conjunctive_rules
    else:
        get_rules = getattr(local_explanation, "get_rules", None)
        rules = get_rules() if callable(get_rules) else getattr(local_explanation, "rules", None)
    if not isinstance(rules, dict):
        raise ValueError("The explanation does not expose alternative-rule data.")
    return rules


def _finite_interval(low: float | None, high: float | None, y_minmax: Any) -> tuple[float | None, float | None]:
    if low is None or high is None:
        return low, high
    if y_minmax is None:
        return low, high
    try:
        min_y = float(y_minmax[0])
        max_y = float(y_minmax[1])
    except (TypeError, ValueError, IndexError):
        return low, high
    if np.isneginf(low):
        low = min_y
    if np.isposinf(high):
        high = max_y
    return low, high


def _ranked_rule_indices(
    local_explanation: Any,
    rules: dict[str, Any],
    prediction: dict[str, Any],
) -> list[int]:
    num_rules = len(list(rules.get("rule", ())))
    if num_rules == 0:
        return []

    predict_values = list(rules.get("predict", ()))
    low_values = list(rules.get("predict_low", ()))
    high_values = list(rules.get("predict_high", ()))
    uncertainties = [
        float(high_values[index]) - float(low_values[index]) for index in range(num_rules)
    ]
    ranking_prediction = list(predict_values)
    base_prediction = float(prediction.get("predict", 0.0))
    is_thresholded = bool(getattr(local_explanation, "is_thresholded", lambda: False)())
    if local_explanation.get_mode() == "classification" or is_thresholded:
        ranking_prediction = [
            float(value) if base_prediction > 0.5 else 1.0 - float(value)
            for value in predict_values
        ]

    ranking = calculate_metrics(
        uncertainty=uncertainties,
        prediction=ranking_prediction,
        w=0.5,
        metric="ensured",
    )
    rank_features = getattr(local_explanation, "rank_features", None)
    if callable(rank_features):
        ordered = rank_features(width=ranking, num_to_show=num_rules)
    else:
        _warn_fallback("rank_features unavailable; using deterministic argsort for rank ordering.")
        ordered = sorted(range(num_rules), key=lambda index: (ranking[index], index))

    ordered_indices = list(reversed([int(index) for index in ordered]))
    filtered_indices: list[int] = []
    for index in ordered_indices:
        if np.isclose(float(predict_values[index]), base_prediction) and np.isclose(
            float(low_values[index]), float(prediction.get("low", 0.0))
        ) and np.isclose(float(high_values[index]), float(prediction.get("high", 0.0))):
            continue
        filtered_indices.append(index)
    return filtered_indices


def _axis_range(values: list[float], *, default: tuple[float, float], include_zero: bool = False) -> list[float]:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    if not finite:
        return [float(default[0]), float(default[1])]
    min_value = min(finite)
    max_value = max(finite)
    if include_zero:
        min_value = min(min_value, 0.0)
        max_value = max(max_value, 0.0)
    if np.isclose(min_value, max_value):
        padding = abs(min_value) * 0.1 or 0.1
        return [min_value - padding, max_value + padding]
    padding = (max_value - min_value) * 0.08
    return [min_value - padding, max_value + padding]


def _build_original_hover(original: dict[str, Any]) -> str:
    lines = ["Original prediction"]
    lines.append(f"Prediction: {original['prediction']:.6g}")
    lines.append(f"Uncertainty: {original['uncertainty']:.6g}")
    if original.get("low") is not None and original.get("high") is not None:
        lines.append(f"Interval: [{original['low']:.6g}, {original['high']:.6g}]")
    return "<br>".join(lines)


def _build_rule_hover(rule_point: dict[str, Any], *, detail: str) -> str:
    lines = [f"Rule: {rule_point['rule']}"]
    lines.append(f"Prediction: {rule_point['prediction']:.6g}")
    lines.append(f"Uncertainty: {rule_point['uncertainty']:.6g}")
    if rule_point.get("low") is not None and rule_point.get("high") is not None:
        lines.append(f"Interval: [{rule_point['low']:.6g}, {rule_point['high']:.6g}]")
    if detail == "full":
        if rule_point.get("feature_name"):
            lines.append(f"Feature: {rule_point['feature_name']}")
        if rule_point.get("feature_index") is not None:
            lines.append(f"Feature index: {rule_point['feature_index']}")
        if rule_point.get("instance_value") is not None:
            lines.append(f"Instance value: {_display_value(rule_point['instance_value'])}")
        if rule_point.get("alternative_value") is not None:
            lines.append(f"Alternative value: {_display_value(rule_point['alternative_value'])}")
        lines.append(f"Delta prediction: {rule_point['delta_prediction']:+.6g}")
        lines.append(f"Delta uncertainty: {rule_point['delta_uncertainty']:+.6g}")
        lines.append(f"Rank: {rule_point['rank']}")
        metadata = rule_point.get("metadata", {})
        if metadata.get("group_label"):
            lines.append(f"Group: {metadata['group_label']}")
        if metadata.get("is_conjunctive") is not None:
            lines.append(f"Conjunctive rule: {metadata['is_conjunctive']}")
    return "<br>".join(lines)


def _sort_rule_points(rule_points: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by == "rank":
        return sorted(rule_points, key=lambda item: (item["rank"], item["index"]))
    if sort_by == "uncertainty":
        return sorted(rule_points, key=lambda item: (-item["uncertainty"], item["index"]))
    if sort_by == "delta_prediction":
        return sorted(
            rule_points,
            key=lambda item: (-abs(item["delta_prediction"]), item["index"]),
        )
    if sort_by == "delta_uncertainty":
        return sorted(
            rule_points,
            key=lambda item: (-abs(item["delta_uncertainty"]), item["index"]),
        )
    if sort_by == "label":
        return sorted(rule_points, key=lambda item: (item["rule"].lower(), item["index"]))
    raise ValueError(
        "sort_by must be one of uncertainty, delta_prediction, delta_uncertainty, rank, or label."
    )


def _triangle_reference_metadata(is_probabilistic: bool) -> dict[str, Any]:
    if is_probabilistic:
        return {
            "enabled": True,
            "kind": "probability_triangle",
            "description": "Probability triangle reference region for alternative predictions.",
        }
    return {
        "enabled": False,
        "kind": "none",
        "description": "Triangle reference is disabled outside probabilistic mode.",
    }


def _rule_groups(rule_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for point in rule_points:
        metadata = point.get("metadata", {})
        group_key = str(metadata.get("group_key", point["id"]))
        group = groups.setdefault(
            group_key,
            {
                "group_key": group_key,
                "group_label": metadata.get("group_label") or group_key,
                "feature_index": point.get("feature_index"),
                "feature_name": point.get("feature_name"),
                "point_ids": [],
            },
        )
        group["point_ids"].append(point["id"])
    return list(groups.values())


class LocalEnsuredTriangularPlotBuilder(PlotBuilder):
    """Build a Plotly artifact for CE's ensured/triangular local alternative plot."""

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
        if intent_type not in (None, "alternative"):
            raise ValueError(
                "plotly.local.ensured_triangular supports alternative local explanations only."
            )

        options = dict(context.options)
        instance_index = options.get("instance_index")
        local_explanation = _select_local_explanation(context.explanation, instance_index)
        if not _is_alternative_explanation(local_explanation):
            raise ValueError(
                "plotly.local.ensured_triangular requires an alternative explanation."
            )

        rules = _resolve_alternative_rules(local_explanation)
        prediction = dict(getattr(local_explanation, "prediction", {}) or {})
        y_minmax = getattr(local_explanation, "y_minmax", None)
        original_low, original_high = _finite_interval(
            _as_float(prediction.get("low")),
            _as_float(prediction.get("high")),
            y_minmax,
        )
        if original_low is None or original_high is None:
            raise ValueError("Alternative explanation is missing calibrated prediction intervals.")

        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        base_prediction = _as_float(prediction.get("predict"))
        if base_prediction is None:
            raise ValueError("Alternative explanation is missing a base prediction.")
        original = {
            "prediction": base_prediction,
            "uncertainty": float(original_high - original_low),
            "low": original_low,
            "high": original_high,
            "label": "Original Prediction",
        }
        original["hover"] = _build_original_hover(original)

        default_rank_order = _ranked_rule_indices(local_explanation, rules, prediction)
        rank_by_index = {rule_index: rank + 1 for rank, rule_index in enumerate(default_rank_order)}

        collection = _collection_for(local_explanation)
        rule_points: list[dict[str, Any]] = []
        missing_rule_metadata_count = 0
        predict_values = list(rules.get("predict", ()))
        low_values = list(rules.get("predict_low", ()))
        high_values = list(rules.get("predict_high", ()))
        feature_values = list(rules.get("feature_value", ()))
        value_values = list(rules.get("value", ()))
        feature_indices = list(rules.get("feature", ()))
        rule_labels = list(rules.get("rule", ()))
        sampled_values = list(rules.get("sampled_values", ()))
        conjunctive_values = list(rules.get("is_conjunctive", ()))

        include_missing_rule_points = bool(options.get("include_missing_rule_points", True))
        hover_detail = str(options.get("hover_detail", "compact"))

        for rule_index in default_rank_order:
            point_low, point_high = _finite_interval(
                _as_float(_sequence_get(low_values, rule_index)),
                _as_float(_sequence_get(high_values, rule_index)),
                y_minmax,
            )
            point_prediction = _as_float(_sequence_get(predict_values, rule_index))
            if point_prediction is None or point_low is None or point_high is None:
                continue

            raw_rule = _sequence_get(rule_labels, rule_index)
            has_rule_metadata = bool(str(raw_rule).strip()) if raw_rule is not None else False
            if not has_rule_metadata:
                missing_rule_metadata_count += 1
                if not include_missing_rule_points:
                    continue
            rule_condition = str(raw_rule).strip() if has_rule_metadata else _RULE_FALLBACK

            feature_index = _sequence_get(feature_indices, rule_index)
            feature_name = _feature_name(collection, feature_index)
            instance_value = _serialise_value(
                _sequence_get(feature_values, rule_index, _sequence_get(value_values, rule_index))
            )
            alternative_value = _serialise_value(_sequence_get(sampled_values, rule_index))
            uncertainty = float(point_high - point_low)
            point = {
                "id": f"rule-point-{rule_index}",
                "index": int(rule_index),
                "feature_index": feature_index,
                "feature_name": feature_name,
                "rule": rule_condition,
                "instance_value": instance_value,
                "alternative_value": alternative_value,
                "prediction": float(point_prediction),
                "uncertainty": uncertainty,
                "low": float(point_low),
                "high": float(point_high),
                "delta_prediction": float(point_prediction - original["prediction"]),
                "delta_uncertainty": float(uncertainty - original["uncertainty"]),
                "rank": rank_by_index[rule_index],
                "metadata": {
                    "group_key": feature_name or str(feature_index) if feature_index is not None else "unknown",
                    "group_label": feature_name or f"Feature {feature_index}"
                    if feature_index is not None
                    else "Unknown feature",
                    "is_conjunctive": bool(_sequence_get(conjunctive_values, rule_index, False)),
                    "rule_metadata_missing": not has_rule_metadata,
                },
            }
            point["hover"] = _build_rule_hover(point, detail=hover_detail)
            rule_points.append(point)

        total_rule_count = len(rule_points)
        sort_by = str(options.get("sort_by", "rank"))
        sorted_rule_points = _sort_rule_points(rule_points, sort_by)

        filter_top = options.get("filter_top")
        if filter_top is None:
            filter_top = options.get("max_points")
        resolved_filter_top = None if filter_top is None else max(0, int(filter_top))
        shown_rule_points = (
            sorted_rule_points
            if resolved_filter_top is None
            else sorted_rule_points[:resolved_filter_top]
        )

        base_spec = build_triangular_plotspec(
            title="Alternative Explanations",
            proba=original["prediction"],
            uncertainty=original["uncertainty"],
            rule_proba=[point["prediction"] for point in shown_rule_points],
            rule_uncertainty=[point["uncertainty"] for point in shown_rule_points],
            num_to_show=len(shown_rule_points),
            is_probabilistic=bool(mode_metadata["is_probabilistic"]),
        )

        arrows = [
            {
                "id": f"arrow-original-to-{point['id']}",
                "from_point_id": _ORIGINAL_POINT_ID,
                "to_point_id": point["id"],
                "x0": original["prediction"],
                "y0": original["uncertainty"],
                "x1": point["prediction"],
                "y1": point["uncertainty"],
                "delta_prediction": point["delta_prediction"],
                "delta_uncertainty": point["delta_uncertainty"],
                "metadata": {
                    "feature_name": point.get("feature_name"),
                    "feature_index": point.get("feature_index"),
                    "rule": point.get("rule"),
                },
            }
            for point in shown_rule_points
        ]

        x_values = [original["prediction"], *[point["prediction"] for point in shown_rule_points]]
        y_values = [original["uncertainty"], *[point["uncertainty"] for point in shown_rule_points]]
        is_probabilistic = bool(mode_metadata["is_probabilistic"])
        axis_metadata = {
            "x_label": "Probability" if is_probabilistic else "Prediction",
            "y_label": "Uncertainty",
            "x_range": [0.0, 1.0] if is_probabilistic else _axis_range(x_values, default=(0.0, 1.0)),
            "y_range": [0.0, 1.0]
            if is_probabilistic
            else _axis_range(y_values, default=(0.0, 1.0), include_zero=True),
            "mode": mode_metadata["mode"],
        }

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": "0.1.0",
            "style": STYLE_ID,
            "base_plotspec_kind": base_spec.kind,
            "mode": mode_metadata["mode"],
            "task": mode_metadata["task"],
            "original": {
                "id": _ORIGINAL_POINT_ID,
                **original,
            },
            "rule_points": shown_rule_points,
            "arrows": arrows,
            "axis_metadata": axis_metadata,
            "triangle_reference_metadata": _triangle_reference_metadata(is_probabilistic),
            "interaction_capabilities": {
                "hover": True,
                "html_export": True,
                "filter_top": True,
                "arrows": True,
                "dropdown_filters": False,
                "click_detail_panel": False,
                "marker_uncertainty_encoding": False,
                "side_table": False,
            },
            "metadata": {
                "filter_top": resolved_filter_top,
                "sort_by": sort_by,
                "shown_rule_count": len(shown_rule_points),
                "total_rule_count": total_rule_count,
                "missing_rule_metadata_count": missing_rule_metadata_count,
                "created_by": STYLE_ID,
                "rule_groups": _rule_groups(rule_points),
            },
        }


def add_triangle_reference(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> None:
    if not bool(options.get("show_triangle_reference", True)):
        return
    metadata = dict(artifact.get("triangle_reference_metadata", {}) or {})
    if not metadata.get("enabled"):
        return

    import plotly.graph_objects as go

    left_y = np.arange(0.0, 1.0, 0.01)
    left_x = left_y / (1.0 + left_y)
    right_x = np.arange(0.5, 1.0, 0.01)
    right_y = (1.0 - right_x) / right_x
    upper_y = np.arange(0.5, 1.0, 0.005)
    upper_x = upper_y / (upper_y + 0.5)
    lower_y = np.arange(0.0, 0.5, 0.005)
    lower_x = 0.5 / (1.0 + lower_y)

    for index, (xs, ys) in enumerate(
        ((left_x, left_y), (right_x, right_y), (upper_x, upper_y - 0.5), (lower_x, lower_y)),
        start=1,
    ):
        fig.add_trace(
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="lines",
                line={"color": "#2f2f2f", "width": 1},
                hoverinfo="skip",
                name=f"triangle-reference-{index}",
                showlegend=False,
            )
        )


def add_original_point(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> None:
    if not bool(options.get("show_original", True)):
        return

    import plotly.graph_objects as go

    original = dict(artifact.get("original", {}) or {})
    fig.add_trace(
        go.Scatter(
            x=[original.get("prediction")],
            y=[original.get("uncertainty")],
            mode="markers",
            marker={"size": 12, "color": _ORIGINAL_COLOR},
            text=[original.get("hover")],
            hovertemplate="%{text}<extra></extra>",
            name="original",
        )
    )


def add_rule_points(fig: Any, artifact: PlotArtifact, _options: dict[str, Any]) -> None:
    import plotly.graph_objects as go

    rule_points = list(artifact.get("rule_points", ()))
    if not rule_points:
        return

    fig.add_trace(
        go.Scatter(
            x=[point.get("prediction") for point in rule_points],
            y=[point.get("uncertainty") for point in rule_points],
            mode="markers",
            marker={"size": 10, "color": _RULE_COLOR},
            text=[point.get("hover") for point in rule_points],
            customdata=[point.get("id") for point in rule_points],
            hovertemplate="%{text}<extra></extra>",
            name="alternatives",
        )
    )


def add_arrows(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> None:
    if not bool(options.get("show_arrows", True)):
        return
    for arrow in artifact.get("arrows", ()): 
        fig.add_annotation(
            x=arrow.get("x1"),
            y=arrow.get("y1"),
            ax=arrow.get("x0"),
            ay=arrow.get("y0"),
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=_ARROW_COLOR,
            opacity=0.9,
        )


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    import plotly.graph_objects as go

    axis_metadata = dict(artifact.get("axis_metadata", {}) or {})
    fig = go.Figure()
    add_triangle_reference(fig, artifact, options)
    add_rule_points(fig, artifact, options)
    add_original_point(fig, artifact, options)
    add_arrows(fig, artifact, options)
    fig.update_layout(
        template="plotly_white",
        title="Local ensured triangular plot",
        xaxis={
            "title": axis_metadata.get("x_label", "Probability"),
            "range": axis_metadata.get("x_range"),
        },
        yaxis={
            "title": axis_metadata.get("y_label", "Uncertainty"),
            "range": axis_metadata.get("y_range"),
        },
        margin={"l": 60, "r": 24, "t": 56, "b": 56},
        showlegend=True,
    )
    return fig


def export_html(fig: Any, path: str) -> str:
    html_path = Path(path)
    if html_path.suffix.lower() != ".html":
        html_path = html_path.with_suffix(".html")
    fig.write_html(str(html_path))
    return str(html_path)


class LocalEnsuredTriangularPlotRenderer(PlotRenderer):
    """Render ensured-triangular artifacts as Plotly figures."""

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
            figure = build_figure(artifact, dict(context.options))
        except ImportError as exc:
            raise RuntimeError(
                "Plotly is required to render plotly.local.ensured_triangular. "
                "Install this package with the [plotly] extra."
            ) from exc

        saved_paths: tuple[str, ...] = ()
        if context.path:
            saved_paths = (export_html(figure, context.path),)
        if context.show:
            figure.show()
        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={"figure": figure},
        )


__all__ = [
    "STYLE_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "LocalEnsuredTriangularPlotBuilder",
    "LocalEnsuredTriangularPlotRenderer",
    "build_figure",
    "add_triangle_reference",
    "add_original_point",
    "add_rule_points",
    "add_arrows",
    "export_html",
]
