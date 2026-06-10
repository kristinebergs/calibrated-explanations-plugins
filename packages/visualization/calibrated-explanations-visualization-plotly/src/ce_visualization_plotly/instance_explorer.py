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
    "regression",
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


def _to_list(values: Any) -> list[Any] | None:
    if values is None:
        return None
    tolist = getattr(values, "tolist", None)
    if callable(tolist):
        values = tolist()
    if isinstance(values, (str, bytes)):
        return [values]
    try:
        return list(values)
    except TypeError:
        return [values]


def _matrix_shape(values: Any) -> tuple[int, int | None]:
    seq = _to_list(values) or []
    if not seq:
        return 0, None
    first = seq[0]
    if isinstance(first, (str, bytes)):
        return len(seq), None
    try:
        return len(seq), len(first)
    except TypeError:
        return len(seq), None


def _matrix_value(values: Any, row: int, column: int | None = None, default: Any = None) -> Any:
    row_value = _sequence_get(values, row, default)
    if column is None:
        return row_value
    return _sequence_get(row_value, column, default)


def _matrix_or_vector_value(
    values: Any, row: int, column: int | None = None, default: Any = None
) -> Any:
    value = _matrix_value(values, row, column, default)
    if value is default and column is not None:
        return _matrix_value(values, row, None, default)
    return value


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


def _payload_from_options(options: dict[str, Any]) -> dict[str, Any] | None:
    payload = options.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


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
            "conformal_regression, regression, or auto."
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


def _confidence_from_percentiles(
    percentiles: tuple[Any, Any] | None, options: dict[str, Any]
) -> Any:
    if options.get("confidence") is not None:
        return options.get("confidence")
    if percentiles is None:
        return None
    low = _as_float(percentiles[0])
    high = _as_float(percentiles[1])
    if low is None or high is None:
        return None
    return max(0.0, high - low)


def _axis_metadata(
    payload: Any, records: list[dict[str, Any]], options: dict[str, Any]
) -> dict[str, Any]:
    task = records[0]["metadata"]["task"] if records else str(options.get("task", "auto"))
    threshold = options.get("threshold")
    percentiles = _option_tuple(options, "low_high_percentiles") or _option_tuple(
        options, "percentiles"
    )
    confidence = options.get("confidence")
    if records:
        threshold = records[0]["metadata"].get("threshold", threshold)
        percentiles = records[0]["metadata"].get("percentiles", percentiles)
        confidence = records[0]["metadata"].get("confidence", confidence)
    if records and records[0]["metadata"].get("x_label"):
        x_label = records[0]["metadata"]["x_label"]
    elif task in {"classification", "probabilistic_regression"}:
        x_label = "Predicted probability"
    elif task == "regression":
        x_label = "Predictions"
    else:
        x_label = "Point prediction / median"
    if task in {"classification", "probabilistic_regression"}:
        y_label = "Calibrated probability interval width"
    else:
        y_label = "Uncertainty"
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


def _class_labels(class_labels: Any, unique_targets: list[Any]) -> list[str]:
    if isinstance(class_labels, dict):
        return [f"Y = {class_labels.get(target, target)}" for target in unique_targets]
    if class_labels is not None:
        labels = _to_list(class_labels) or []
        if labels:
            return [f"Y = {label}" for label in labels]
    return [f"Y = {target}" for target in unique_targets]


def _threshold_xlabel(threshold: Any) -> str:
    if isinstance(threshold, (tuple, list)) and len(threshold) >= 2:
        return f"Probability of {threshold[0]} <= Y < {threshold[1]}"
    return f"Probability of Y < {threshold}"


def _threshold_target_class(target: Any, threshold: Any) -> tuple[int | None, str | None]:
    value = _as_float(target)
    threshold_value = _as_float(threshold)
    if value is None or threshold_value is None:
        return None, None
    if value < threshold_value:
        return 1, f"Y < {threshold}"
    return 0, f"Y >= {threshold}"


def _records_from_global_payload(
    payload: dict[str, Any], options: dict[str, Any]
) -> list[dict[str, Any]]:
    proba = payload.get("proba")
    predict = payload.get("predict")
    low = payload.get("low")
    high = payload.get("high")
    uncertainty = payload.get("uncertainty")
    y_values = payload.get("y_test", payload.get("y"))
    threshold = options.get("threshold", payload.get("threshold"))
    is_regularized = bool(payload.get("is_regularized", proba is not None))
    class_labels = payload.get("class_labels")
    target_values = _to_list(y_values)
    proba_rows, proba_cols = _matrix_shape(proba)
    predict_values = _to_list(predict)
    rows = proba_rows or _sequence_len(predict_values) or _sequence_len(_to_list(low)) or 0
    if rows == 0:
        raise ValueError("plotly.global.instance_explorer requires global plot predictions.")

    task_option = str(options.get("task", "auto"))
    if task_option != "auto":
        task = task_option
    elif is_regularized and threshold is not None:
        task = "probabilistic_regression"
    elif is_regularized:
        task = "classification"
    else:
        task = "regression"
    if task == "regression":
        is_regularized = False

    unique_targets = sorted(set(target_values), key=lambda item: str(item)) if target_values else []
    target_labels = _class_labels(class_labels, unique_targets)
    target_label_lookup = {
        str(target): target_labels[index] if index < len(target_labels) else f"Y = {target}"
        for index, target in enumerate(unique_targets)
    }

    records: list[dict[str, Any]] = []
    for index in range(rows):
        target = _sequence_get(target_values, index) if target_values is not None else None
        selected_column: int | None = None
        predicted_class = None
        x_label = "Predictions"
        if is_regularized:
            if threshold is not None:
                selected_column = 1 if proba_cols and proba_cols > 1 else 0 if proba_cols else None
                x_label = _threshold_xlabel(threshold)
            elif proba_cols and proba_cols > 1:
                if target is None:
                    if proba_cols == 2:
                        selected_column = 1
                        x_label = "Probability of Y = 1"
                    else:
                        row_values = [
                            _as_float(_matrix_value(proba, index, column))
                            for column in range(proba_cols)
                        ]
                        selected_column = max(
                            range(proba_cols),
                            key=lambda column: row_values[column]
                            if row_values[column] is not None
                            else float("-inf"),
                        )
                        predicted_class = selected_column
                        x_label = "Probability of Y = predicted class"
                elif proba_cols == 2 or len(unique_targets) == 2:
                    selected_column = 1
                    x_label = "Probability of Y = 1"
                else:
                    selected_column = int(target)
                    x_label = "Probability of Y = actual class"
            prediction_value = _as_float(_matrix_value(proba, index, selected_column))
            low_value = _as_float(_matrix_or_vector_value(low, index, selected_column))
            high_value = _as_float(_matrix_or_vector_value(high, index, selected_column))
            uncertainty_value = _as_float(
                _matrix_or_vector_value(uncertainty, index, selected_column)
            )
        else:
            prediction_value = _as_float(_sequence_get(predict_values, index))
            low_value = _as_float(_matrix_value(low, index))
            high_value = _as_float(_matrix_value(high, index))
            uncertainty_value = _as_float(_matrix_value(uncertainty, index))
        if prediction_value is None:
            continue
        if uncertainty_value is None and low_value is not None and high_value is not None:
            uncertainty_value = high_value - low_value
        if low_value is None and high_value is None and uncertainty_value is not None:
            low_value = prediction_value - uncertainty_value / 2.0
            high_value = prediction_value + uncertainty_value / 2.0
        if low_value is None or high_value is None or uncertainty_value is None:
            raise ValueError(
                "plotly.global.instance_explorer requires low/high or uncertainty values."
            )
        target_metadata_value = target
        target_label = (
            target_label_lookup.get(str(target), f"Y = {target}") if target is not None else None
        )
        if task == "probabilistic_regression" and target is not None:
            threshold_class, threshold_label = _threshold_target_class(target, threshold)
            if threshold_class is not None:
                target_metadata_value = threshold_class
                target_label = threshold_label
        true_label = (
            target_metadata_value
            if task in {"classification", "probabilistic_regression"}
            else None
        )
        target_value = target if task == "regression" else None
        records.append(
            {
                "instance_index": index,
                "x": float(prediction_value),
                "y": float(uncertainty_value),
                "prediction": float(prediction_value),
                "probability": float(prediction_value) if is_regularized else None,
                "low": float(low_value),
                "high": float(high_value),
                "interval_width": float(uncertainty_value),
                "predicted_class": predicted_class,
                "true_label": true_label,
                "target_value": target_value,
                "metadata": {
                    "task": task,
                    "posture": task,
                    "class_id": selected_column,
                    "threshold": threshold,
                    "percentiles": options.get("low_high_percentiles"),
                    "confidence": options.get("confidence"),
                    "x_label": x_label,
                    "target": target_metadata_value,
                    "raw_target": target,
                    "target_label": target_label,
                    "target_kind": "continuous"
                    if task == "regression" and target is not None
                    else "class",
                    "is_aggregated_marker": False,
                },
            }
        )
    if not records:
        raise ValueError(
            "No global prediction records were available for plotly.global.instance_explorer."
        )
    return records


def build_instance_records(payload: Any, options: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one record per instance before deterministic position aggregation."""
    global_payload = _payload_from_options(options)
    if global_payload is not None:
        return _records_from_global_payload(global_payload, options)

    records: list[dict[str, Any]] = []
    for index, item in enumerate(_local_explanations(payload)):
        prediction = _prediction_dict(item)
        if not prediction:
            continue
        task = _resolve_task(payload, item, options)
        low = _as_float(prediction.get("low"))
        high = _as_float(prediction.get("high"))
        if low is None or high is None:
            raise ValueError(
                "plotly.global.instance_explorer requires calibrated low/high intervals."
            )

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
        raise ValueError(
            "No batch prediction records were available for plotly.global.instance_explorer."
        )
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


def _aggregation_group_key(record: dict[str, Any], options: dict[str, Any]) -> tuple[Any, ...]:
    key = _aggregation_key(record, options)
    task = record.get("metadata", {}).get("task")
    target = record.get("metadata", {}).get("target")
    if target is not None and task in {"classification", "probabilistic_regression"}:
        return (key[0], key[1], "target", str(target))
    return (key[0], key[1])


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
    return {
        str(key): count
        for key, count in sorted(Counter(values).items(), key=lambda item: str(item[0]))
    }


def _summarize_group(records: list[dict[str, Any]], task: str) -> dict[str, Any]:
    predictions = [record["prediction"] for record in records]
    lows = [record["low"] for record in records]
    highs = [record["high"] for record in records]
    widths = [record["interval_width"] for record in records]
    predicted_classes = [
        record.get("predicted_class")
        for record in records
        if record.get("predicted_class") is not None
    ]
    true_labels = [
        record.get("true_label") for record in records if record.get("true_label") is not None
    ]
    target_values = [
        record.get("target_value") for record in records if record.get("target_value") is not None
    ]
    summary = {
        "prediction_summary": {
            "mean": _mean(predictions),
            "min": min(predictions),
            "max": max(predictions),
        },
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
            observed = sum(
                1
                for value in target_values
                if _as_float(value) is not None and float(value) <= threshold_float
            )
            summary["target_summary"] = {
                "threshold": threshold,
                "observed_event_count": observed,
                "observed_non_event_count": len(target_values) - observed,
            }
    if task == "regression" and target_values:
        numeric_targets = [_as_float(value) for value in target_values]
        numeric_targets = [value for value in numeric_targets if value is not None]
        summary["target_summary"] = {
            "target_mean": _mean(numeric_targets),
            "target_min": min(numeric_targets) if numeric_targets else None,
            "target_max": max(numeric_targets) if numeric_targets else None,
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
                f"Correct / incorrect: {class_summary['num_correct']} / {class_summary['num_incorrect']}"  # noqa: E501
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
    elif task == "conformal_regression":
        percentiles = metadata.get("percentiles")
        confidence = metadata.get("confidence")
        lines.extend(
            [
                f"Point prediction / median: {prediction['mean']:.6g}",
                f"Percentiles: {percentiles[0]} / {percentiles[1]}"
                if percentiles
                else "Percentiles: unavailable",
                f"Confidence: {confidence:g}%"
                if _as_float(confidence) is not None
                else "Confidence: unavailable",
                f"Prediction interval: [{interval['low_mean']:.6g}, {interval['high_mean']:.6g}]",
                f"Interval width: {interval['width_mean']:.6g}",
            ]
        )
        inside = marker_record.get("target_summary", {}).get("observed_inside_interval")
        if inside is not None:
            lines.append(f"Observed inside interval: {inside} / {count}")
    else:
        lines.extend(
            [
                f"Prediction: {prediction['mean']:.6g}",
                f"Prediction interval: [{interval['low_mean']:.6g}, {interval['high_mean']:.6g}]",
                f"Uncertainty: {interval['width_mean']:.6g}",
            ]
        )
        target_mean = marker_record.get("target_summary", {}).get("target_mean")
        if target_mean is not None:
            lines.append(f"Mean target: {target_mean:.6g}")
    return "<br>".join(lines)


def aggregate_instance_records(
    records: list[dict[str, Any]], options: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _aggregation_group_key(record, options)
        groups[key].append(record)

    max_count = max(len(group) for group in groups.values())
    markers: list[dict[str, Any]] = []
    for marker_index, key in enumerate(
        sorted(groups, key=lambda item: (float(item[0]), float(item[1]), str(item[2:])))
    ):
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
    if axis_metadata.get("is_probabilistic"):
        figure.update_layout(xaxis={"range": [0.0, 1.0]}, yaxis={"range": [0.0, 1.0]})
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
    import plotly.graph_objects as go

    markers = list(artifact.get("marker_records", ()))
    target_metadata = dict(artifact.get("target_metadata", {}) or {})
    target_kind = target_metadata.get("target_kind")
    if target_kind == "class":
        symbols = [
            "circle",
            "x",
            "square",
            "triangle-up",
            "triangle-down",
            "diamond",
            "cross",
            "star",
            "hexagon",
        ]
        colors = [
            "#1f77b4",
            "#d62728",
            "#2ca02c",
            "#ff7f0e",
            "#9467bd",
            "#8c564b",
            "#17becf",
            "#7f7f7f",
        ]
        targets = list(target_metadata.get("targets", ()))
        target_styles = {
            str(target): {
                "color": colors[index % len(colors)],
                "symbol": symbols[index % len(symbols)],
                "label": target_metadata.get("target_labels", {}).get(str(target), f"Y = {target}"),
            }
            for index, target in enumerate(targets)
        }
        for _index, target in enumerate(targets):
            style = target_styles[str(target)]
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker={
                        "size": 10,
                        "color": style["color"],
                        "symbol": style["symbol"],
                        "line": {"color": "white", "width": 1},
                    },
                    hoverinfo="skip",
                    name=style["label"],
                    meta={"trace_kind": "target-legend", "target": target},
                )
            )
        sorted_markers = sorted(
            markers,
            key=lambda marker: (
                -float(marker.get("marker_size", 0.0)),
                -int(marker.get("count", 0)),
                str(marker.get("metadata", {}).get("target")),
                int(marker.get("instance_indices", [0])[0]),
            ),
        )
        marker_symbols = [
            target_styles[str(marker.get("metadata", {}).get("target"))]["symbol"]
            for marker in sorted_markers
        ]
        marker_colors = [
            target_styles[str(marker.get("metadata", {}).get("target"))]["color"]
            for marker in sorted_markers
        ]
        fig.add_trace(
            go.Scatter(
                x=[marker["x"] for marker in sorted_markers],
                y=[marker["y"] for marker in sorted_markers],
                mode="markers",
                marker={
                    "size": [marker["marker_size"] for marker in sorted_markers],
                    "color": marker_colors,
                    "symbol": marker_symbols,
                    "line": {"color": "white", "width": 1},
                },
                text=[marker["hover"] for marker in sorted_markers],
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
                name="instances",
                meta={"trace_kind": "instances", "draw_order": "marker_size_desc"},
            )
        )
        return

    marker_color: Any = [marker["count"] for marker in markers]
    colorbar_title = "Instances"
    showscale = True
    if target_kind == "continuous":
        marker_color = [marker.get("target_summary", {}).get("target_mean") for marker in markers]
        colorbar_title = "Target"
    fig.add_trace(
        go.Scatter(
            x=[marker["x"] for marker in markers],
            y=[marker["y"] for marker in markers],
            mode="markers",
            marker={
                "size": [marker["marker_size"] for marker in markers],
                "color": marker_color,
                "colorscale": "Viridis",
                "showscale": showscale,
                "colorbar": {"title": colorbar_title},
                "line": {"color": "white", "width": 1},
            },
            text=[marker["hover"] for marker in markers],
            hovertemplate="%{text}<extra></extra>",
            name="instances",
        )
    )


def _target_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [record.get("metadata", {}).get("target") for record in records]
    targets = [target for target in targets if target is not None]
    if not targets:
        return {"provided": False, "target_kind": None, "targets": (), "target_labels": {}}
    task = records[0]["metadata"]["task"]
    if task == "regression":
        return {"provided": True, "target_kind": "continuous", "targets": (), "target_labels": {}}
    unique_targets = sorted(set(targets), key=lambda item: str(item))
    labels = {
        str(target): next(
            (
                record.get("metadata", {}).get("target_label")
                for record in records
                if str(record.get("metadata", {}).get("target")) == str(target)
            ),
            f"Y = {target}",
        )
        for target in unique_targets
    }
    return {
        "provided": True,
        "target_kind": "class",
        "targets": tuple(unique_targets),
        "target_labels": labels,
    }


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
            raise ValueError(
                "marker_size_mode must be 'count' for plotly.global.instance_explorer v1."
            )
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
            "target_metadata": _target_metadata(records),
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
