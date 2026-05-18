from __future__ import annotations

import logging
import math
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)

STYLE_ID = "plotly.global.instance_explorer"
BUILDER_ID = "official.visualization.plotly.global.instance_explorer.builder"
RENDERER_ID = "official.visualization.plotly.global.instance_explorer.renderer"
ARTIFACT_TYPE = STYLE_ID
ARTIFACT_VERSION = "0.1.0"

_LOGGER = logging.getLogger(__name__)
_VALID_TASKS = {
    "auto",
    "classification",
    "probabilistic_regression",
    "conformal_regression",
}


def _warn_fallback(reason: str) -> None:
    message = f"Plotly global instance explorer fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _sequence_get(values: Any, index: int, default: Any = None) -> Any:
    if values is None:
        return default
    try:
        return values[index]
    except (IndexError, KeyError, TypeError):
        return default


def _sequence_len(values: Any) -> int | None:
    try:
        return len(values)
    except TypeError:
        return None


def _option_tuple(options: dict[str, Any], name: str) -> tuple[Any, Any] | None:
    value = options.get(name)
    if value is None:
        return None
    try:
        first, second = value
    except (TypeError, ValueError):
        return None
    return first, second


def _prediction_dict(item: Any) -> dict[str, Any]:
    prediction = getattr(item, "prediction", None)
    if prediction is None and isinstance(item, dict):
        prediction = item.get("prediction", item)
    return dict(prediction or {}) if isinstance(prediction, dict) else {}


def _collection_for(payload: Any) -> Any:
    return getattr(payload, "calibrated_explanations", payload)


def _batch_metadata(payload: Any) -> dict[str, Any]:
    collection = _collection_for(payload)
    metadata = getattr(collection, "batch_metadata", None)
    if metadata is None and isinstance(payload, dict):
        metadata = payload.get("batch_metadata") or payload.get("metadata")
    return dict(metadata or {}) if isinstance(metadata, dict) else {}


def _local_explanations(payload: Any) -> list[Any]:
    explanations = getattr(payload, "explanations", None)
    if explanations is not None:
        return list(explanations)
    if isinstance(payload, dict):
        explanations = payload.get("explanations") or payload.get("instances")
        if explanations is not None:
            return list(explanations)
    return [payload]


def _resolve_task(payload: Any, item: Any, options: dict[str, Any]) -> str:
    explicit_task = str(options.get("task", "auto"))
    if explicit_task not in _VALID_TASKS:
        raise ValueError(
            "task must be one of classification, probabilistic_regression, "
            "conformal_regression, or auto."
        )
    if explicit_task != "auto":
        return explicit_task

    metadata = _batch_metadata(payload)
    raw_task = metadata.get("task") or metadata.get("mode")
    get_mode = getattr(item, "get_mode", None)
    raw_mode = get_mode() if callable(get_mode) else raw_task
    is_thresholded = getattr(item, "is_thresholded", None)
    if callable(is_thresholded) and bool(is_thresholded()):
        return "probabilistic_regression"
    if options.get("threshold") is not None or metadata.get("y_threshold") is not None:
        return "probabilistic_regression"
    if str(raw_mode).lower() == "classification" or str(raw_task).lower() == "classification":
        return "classification"
    return "conformal_regression"


def _class_probability(
    prediction: dict[str, Any],
    *,
    instance_index: int,
    class_id: Any,
) -> float | None:
    full = prediction.get("__full_probabilities__")
    if full is None:
        full = prediction.get("probabilities")
    if class_id is not None and full is not None:
        row = _sequence_get(full, instance_index)
        value = _sequence_get(row, int(class_id), None)
        selected = _as_float(value)
        if selected is not None:
            return selected
    return _as_float(prediction.get("predict"))


def _predicted_class(prediction: dict[str, Any], probability: float | None, class_id: Any) -> Any:
    if class_id is not None:
        return class_id
    predicted = prediction.get("predicted_class", prediction.get("classes"))
    if predicted is not None:
        return predicted
    if probability is None:
        return None
    return int(probability >= 0.5)


def _truth_value(payload: Any, item: Any, options: dict[str, Any], index: int, *names: str) -> Any:
    for name in names:
        if name in options:
            return _sequence_get(options.get(name), index)
        if isinstance(payload, dict) and name in payload:
            return _sequence_get(payload.get(name), index)
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _threshold_for(payload: Any, item: Any, options: dict[str, Any]) -> Any:
    metadata = _batch_metadata(payload)
    return (
        options.get("threshold")
        if options.get("threshold") is not None
        else getattr(item, "y_threshold", metadata.get("y_threshold"))
    )


def _percentiles_for(payload: Any, item: Any, options: dict[str, Any]) -> tuple[Any, Any] | None:
    metadata = _batch_metadata(payload)
    return (
        _option_tuple(options, "low_high_percentiles")
        or _option_tuple(options, "percentiles")
        or getattr(item, "low_high_percentiles", None)
        or metadata.get("low_high_percentiles")
    )


def _confidence_from_percentiles(percentiles: tuple[Any, Any] | None, options: dict[str, Any]) -> Any:
    if options.get("confidence") is not None:
        return options.get("confidence")
    if percentiles is None:
        return None
    low = _as_float(percentiles[0])
    high = _as_float(percentiles[1])
    if low is None or high is None:
        return None
    return max(0.0, high - low)


def _axis_metadata(payload: Any, records: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    task = records[0]["metadata"]["task"] if records else str(options.get("task", "auto"))
    threshold = options.get("threshold")
    percentiles = _option_tuple(options, "low_high_percentiles") or _option_tuple(options, "percentiles")
    confidence = options.get("confidence")
    if records:
        threshold = records[0]["metadata"].get("threshold", threshold)
        percentiles = records[0]["metadata"].get("percentiles", percentiles)
        confidence = records[0]["metadata"].get("confidence", confidence)
    if task in {"classification", "probabilistic_regression"}:
        x_label = "Predicted probability"
        y_label = "Calibrated probability interval width"
    else:
        x_label = "Point prediction / median"
        y_label = "Calibrated prediction interval width"
    return {
        "x_label": x_label,
        "y_label": y_label,
        "task": task,
        "posture": task,
        "is_probabilistic": task in {"classification", "probabilistic_regression"},
        "class_id": options.get("class_id"),
        "threshold": threshold,
        "percentiles": percentiles,
        "confidence": confidence,
    }


def _triangle_reference_metadata(task: str) -> dict[str, Any]:
    enabled = task in {"classification", "probabilistic_regression"}
    return {
        "enabled": enabled,
        "kind": "probability_triangle" if enabled else None,
        "description": (
            "Probability triangle reference region for probabilistic batch predictions."
            if enabled
            else "Triangle reference is disabled outside probabilistic posture."
        ),
    }


def build_instance_records(payload: Any, options: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one record per instance before deterministic position aggregation."""
    records: list[dict[str, Any]] = []
    for index, item in enumerate(_local_explanations(payload)):
        prediction = _prediction_dict(item)
        if not prediction:
            continue
        task = _resolve_task(payload, item, options)
        low = _as_float(prediction.get("low"))
        high = _as_float(prediction.get("high"))
        if low is None or high is None:
            raise ValueError("plotly.global.instance_explorer requires calibrated low/high intervals.")

        class_id = options.get("class_id")
        threshold = _threshold_for(payload, item, options)
        percentiles = _percentiles_for(payload, item, options)
        confidence = _confidence_from_percentiles(percentiles, options)
        true_label = _truth_value(payload, item, options, index, "true_labels", "y_true", "labels")
        target_value = _truth_value(payload, item, options, index, "target_values", "targets", "y")

        if task == "classification":
            probability = _class_probability(prediction, instance_index=index, class_id=class_id)
            if probability is None:
                continue
            predicted_class = _predicted_class(prediction, probability, class_id)
            x_value = probability
        else:
            x_value = _as_float(prediction.get("predict"))
            predicted_class = None
            probability = x_value if task == "probabilistic_regression" else None
        if x_value is None:
            continue
        width = high - low

        records.append(
            {
                "instance_index": index,
                "x": float(x_value),
                "y": float(width),
                "prediction": float(x_value),
                "probability": probability,
                "low": float(low),
                "high": float(high),
                "interval_width": float(width),
                "predicted_class": predicted_class,
                "true_label": true_label,
                "target_value": target_value,
                "metadata": {
                    "task": task,
                    "posture": task,
                    "class_id": class_id,
                    "threshold": threshold,
                    "percentiles": percentiles,
                    "confidence": confidence,
                    "is_aggregated_marker": False,
                },
            }
        )
    if not records:
        raise ValueError("No batch prediction records were available for plotly.global.instance_explorer.")
    return records


def _aggregation_key(record: dict[str, Any], options: dict[str, Any]) -> tuple[float, float]:
    if not bool(options.get("aggregate_positions", True)):
        return (record["instance_index"], record["instance_index"])
    precision = int(options.get("position_precision", 3))
    strategy = str(options.get("aggregation_strategy", "round"))
    if strategy == "round":
        return (round(float(record["x"]), precision), round(float(record["y"]), precision))
    if strategy == "bin":
        step = 10 ** (-precision)
        return (
            math.floor(float(record["x"]) / step) * step,
            math.floor(float(record["y"]) / step) * step,
        )
    raise ValueError("aggregation_strategy must be 'round' or 'bin'.")


def _marker_size(count: int, max_count: int, options: dict[str, Any]) -> float:
    minimum = float(options.get("marker_size_min", 6))
    maximum = float(options.get("marker_size_max", 32))
    if count <= 1 or max_count <= 1 or maximum <= minimum:
        return minimum
    scale = (math.sqrt(count) - 1.0) / (math.sqrt(max_count) - 1.0)
    return minimum + scale * (maximum - minimum)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _format_counter(values: list[Any]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(Counter(values).items(), key=lambda item: str(item[0]))}


def _summarize_group(records: list[dict[str, Any]], task: str) -> dict[str, Any]:
    predictions = [record["prediction"] for record in records]
    lows = [record["low"] for record in records]
    highs = [record["high"] for record in records]
    widths = [record["interval_width"] for record in records]
    predicted_classes = [record.get("predicted_class") for record in records if record.get("predicted_class") is not None]
    true_labels = [record.get("true_label") for record in records if record.get("true_label") is not None]
    target_values = [record.get("target_value") for record in records if record.get("target_value") is not None]
    summary = {
        "prediction_summary": {"mean": _mean(predictions), "min": min(predictions), "max": max(predictions)},
        "interval_summary": {
            "low_mean": _mean(lows),
            "high_mean": _mean(highs),
            "width_mean": _mean(widths),
            "width_min": min(widths),
            "width_max": max(widths),
        },
        "class_summary": {},
        "target_summary": {},
    }
    if task == "classification":
        correct = sum(
            1
            for record in records
            if record.get("true_label") is not None
            and str(record.get("true_label")) == str(record.get("predicted_class"))
        )
        summary["class_summary"] = {
            "predicted_class_distribution": _format_counter(predicted_classes),
            "true_label_distribution": _format_counter(true_labels),
            "num_correct": correct if true_labels else None,
            "num_incorrect": len(true_labels) - correct if true_labels else None,
        }
    if task == "probabilistic_regression":
        threshold = records[0]["metadata"].get("threshold")
        threshold_float = _as_float(threshold)
        if threshold_float is not None and target_values:
            observed = sum(1 for value in target_values if _as_float(value) is not None and float(value) <= threshold_float)
            summary["target_summary"] = {
                "threshold": threshold,
                "observed_event_count": observed,
                "observed_non_event_count": len(target_values) - observed,
            }
    if task == "conformal_regression" and target_values:
        inside = sum(
            1
            for record in records
            if _as_float(record.get("target_value")) is not None
            and record["low"] <= float(record["target_value"]) <= record["high"]
        )
        summary["target_summary"] = {
            "observed_inside_interval": inside,
            "observed_outside_interval": len(target_values) - inside,
        }
    return summary


def build_hover_text(marker_record: dict[str, Any], task: str, options: dict[str, Any]) -> str:
    """Build task-specific hover text for an aggregated marker."""
    del options
    count = marker_record["count"]
    interval = marker_record["interval_summary"]
    prediction = marker_record["prediction_summary"]
    metadata = marker_record.get("metadata", {})
    lines = [f"Instances: {count}"]
    if task == "classification":
        class_summary = marker_record.get("class_summary", {})
        class_distribution = class_summary.get("predicted_class_distribution", {})
        predicted_class = next(iter(class_distribution.keys()), metadata.get("class_id"))
        lines.extend(
            [
                f"Predicted class: {predicted_class}",
                f"Probability: {prediction['mean']:.6g}",
                f"Probability interval: [{interval['low_mean']:.6g}, {interval['high_mean']:.6g}]",
                f"Interval width: {interval['width_mean']:.6g}",
            ]
        )
        true_distribution = class_summary.get("true_label_distribution")
        if true_distribution:
            lines.append(f"True labels: {true_distribution}")
        if class_summary.get("num_correct") is not None:
            lines.append(
                f"Correct / incorrect: {class_summary['num_correct']} / {class_summary['num_incorrect']}"
            )
    elif task == "probabilistic_regression":
        threshold = metadata.get("threshold")
        event = f"y <= {threshold}" if threshold is not None else "threshold event"
        lines.extend(
            [
                f"Target event: {event}",
                f"Probability: {prediction['mean']:.6g}",
                f"Probability interval: [{interval['low_mean']:.6g}, {interval['high_mean']:.6g}]",
                f"Interval width: {interval['width_mean']:.6g}",
            ]
        )
        observed = marker_record.get("target_summary", {}).get("observed_event_count")
        if observed is not None:
            lines.append(f"Observed event count: {observed} / {count}")
    else:
        percentiles = metadata.get("percentiles")
        confidence = metadata.get("confidence")
        lines.extend(
            [
                f"Point prediction / median: {prediction['mean']:.6g}",
                f"Percentiles: {percentiles[0]} / {percentiles[1]}" if percentiles else "Percentiles: unavailable",
                f"Confidence: {confidence:g}%" if _as_float(confidence) is not None else "Confidence: unavailable",
                f"Prediction interval: [{interval['low_mean']:.6g}, {interval['high_mean']:.6g}]",
                f"Interval width: {interval['width_mean']:.6g}",
            ]
        )
        inside = marker_record.get("target_summary", {}).get("observed_inside_interval")
        if inside is not None:
            lines.append(f"Observed inside interval: {inside} / {count}")
    return "<br>".join(lines)


def aggregate_instance_records(records: list[dict[str, Any]], options: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _aggregation_key(record, options)
        groups[key].append(record)

    max_count = max(len(group) for group in groups.values())
    markers: list[dict[str, Any]] = []
    for marker_index, key in enumerate(sorted(groups, key=lambda item: (float(item[0]), float(item[1])))):
        group = groups[key]
        task = group[0]["metadata"]["task"]
        count = len(group)
        summary = _summarize_group(group, task)
        marker = {
            "marker_id": f"marker-{marker_index}",
            "x": float(key[0]) if bool(options.get("aggregate_positions", True)) else group[0]["x"],
            "y": float(key[1]) if bool(options.get("aggregate_positions", True)) else group[0]["y"],
            "count": count,
            "marker_size": _marker_size(count, max_count, options),
            "instance_indices": [record["instance_index"] for record in group],
            "metadata": {
                **group[0]["metadata"],
                "represents_multiple_instances": count > 1,
                "is_aggregated_marker": count > 1,
                "aggregation_key": key,
            },
            **summary,
        }
        marker["hover"] = build_hover_text(marker, task, options)
        markers.append(marker)
    return markers


def _artifact_options(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "aggregate_positions": bool(options.get("aggregate_positions", True)),
        "position_precision": int(options.get("position_precision", 3)),
        "aggregation_strategy": str(options.get("aggregation_strategy", "round")),
        "marker_size_mode": str(options.get("marker_size_mode", "count")),
        "marker_size_min": float(options.get("marker_size_min", 6)),
        "marker_size_max": float(options.get("marker_size_max", 32)),
        "show_individual_points": bool(options.get("show_individual_points", False)),
        "include_instance_records": bool(options.get("include_instance_records", False)),
        "show_triangle_reference": bool(options.get("show_triangle_reference", True)),
    }


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    import plotly.graph_objects as go

    figure = go.Figure()
    add_triangle_reference(figure, artifact, options)
    add_marker_trace(figure, artifact, options)
    axis_metadata = artifact["axis_metadata"]
    figure.update_layout(
        template="plotly_white",
        title="Batch prediction/uncertainty instance explorer",
        xaxis_title=axis_metadata["x_label"],
        yaxis_title=axis_metadata["y_label"],
        margin={"l": 64, "r": 24, "t": 56, "b": 56},
    )
    return figure


def _trace_count(fig: Any) -> int:
    if hasattr(fig, "data"):
        return len(fig.data)
    return len(getattr(fig, "traces", ()))


def add_triangle_reference(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> list[int]:
    if not bool(options.get("show_triangle_reference", True)):
        return []
    metadata = dict(artifact.get("triangle_reference_metadata", {}) or {})
    if not metadata.get("enabled"):
        return []

    import plotly.graph_objects as go

    trace_indexes: list[int] = []
    left_y = [index / 100.0 for index in range(0, 100)]
    left_x = [value / (1.0 + value) for value in left_y]
    right_x = [0.5 + index / 100.0 for index in range(0, 50)]
    right_y = [(1.0 - value) / value for value in right_x]
    upper_y = [0.5 + index / 200.0 for index in range(0, 100)]
    upper_x = [value / (value + 0.5) for value in upper_y]
    lower_y = [index / 200.0 for index in range(0, 100)]
    lower_x = [0.5 / (1.0 + value) for value in lower_y]

    for index, (xs, ys) in enumerate(
        (
            (left_x, left_y),
            (right_x, right_y),
            (upper_x, [value - 0.5 for value in upper_y]),
            (lower_x, lower_y),
        ),
        start=1,
    ):
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"color": "#2f2f2f", "width": 1},
                hoverinfo="skip",
                meta={"trace_kind": "triangle-reference"},
                name=f"triangle-reference-{index}",
                showlegend=False,
            )
        )
        trace_indexes.append(_trace_count(fig) - 1)
    return trace_indexes


def add_marker_trace(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> None:
    del options
    markers = list(artifact.get("marker_records", ()))
    fig.add_trace(
        __import__("plotly.graph_objects", fromlist=["Scatter"]).Scatter(
            x=[marker["x"] for marker in markers],
            y=[marker["y"] for marker in markers],
            mode="markers",
            marker={
                "size": [marker["marker_size"] for marker in markers],
                "color": [marker["count"] for marker in markers],
                "colorscale": "Viridis",
                "showscale": True,
                "colorbar": {"title": "Instances"},
                "line": {"color": "white", "width": 1},
            },
            text=[marker["hover"] for marker in markers],
            hovertemplate="%{text}<extra></extra>",
            name="instances",
        )
    )


def export_html(fig: Any, path: str | Path) -> str:
    html_path = Path(path)
    if html_path.suffix.lower() != ".html":
        html_path = html_path.with_suffix(".html")
    fig.write_html(str(html_path))
    return str(html_path)


class GlobalInstanceExplorerPlotBuilder(PlotBuilder):
    """Build a hover-only batch prediction/uncertainty overview artifact."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.global",
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
        options = {**_artifact_options(dict(context.options)), **dict(context.options)}
        if str(options.get("marker_size_mode", "count")) != "count":
            raise ValueError("marker_size_mode must be 'count' for plotly.global.instance_explorer v1.")
        records = build_instance_records(context.explanation, options)
        markers = aggregate_instance_records(records, options)
        counts = [marker["count"] for marker in markers]
        artifact: PlotArtifact = {
            "artifact_type": ARTIFACT_TYPE,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "axis_metadata": _axis_metadata(context.explanation, records, options),
            "triangle_reference_metadata": _triangle_reference_metadata(
                records[0]["metadata"]["task"]
            ),
            "marker_records": markers,
            "aggregation_metadata": {
                "aggregate_positions": bool(options.get("aggregate_positions", True)),
                "aggregation_strategy": str(options.get("aggregation_strategy", "round")),
                "position_precision": int(options.get("position_precision", 3)),
                "num_instances": len(records),
                "num_markers": len(markers),
                "max_count": max(counts),
                "min_count": min(counts),
            },
            "interaction_capabilities": {
                "hover": True,
                "html_export": True,
                "click_panel": False,
                "narrative_panel": False,
                "local_plot_panel": False,
                "aggregation": True,
            },
            "options": _artifact_options(options),
        }
        if bool(options.get("include_instance_records", False)):
            artifact["instance_records"] = records
        return artifact


class GlobalInstanceExplorerPlotRenderer(PlotRenderer):
    """Render hover-only batch instance explorer artifacts as Plotly figures."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.global",
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": ("plotly",),
        "trusted": False,
        "trust": False,
        "supports_interactive": True,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        if artifact.get("artifact_type") != ARTIFACT_TYPE:
            _warn_fallback("received an unexpected artifact type; rendering with available fields.")
        try:
            figure = build_figure(artifact, dict(context.options))
        except ImportError as exc:
            raise RuntimeError(
                "Plotly is required to render plotly.global.instance_explorer. "
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
