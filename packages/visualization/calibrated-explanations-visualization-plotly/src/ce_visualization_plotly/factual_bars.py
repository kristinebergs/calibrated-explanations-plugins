from __future__ import annotations

import contextlib
import logging
import re
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)

STYLE_ID = "plotly.local.factual_bars"
BUILDER_ID = "official.visualization.plotly.local.factual_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.factual_bars.renderer"
ARTIFACT_VERSION = "0.1.0"

_LOGGER = logging.getLogger(__name__)
# Task-specific bar colors matching matplotlib tab palette for visual parity.
# Classification: positive contribution → red, negative → blue (CE default).
# Regression: positive contribution → blue, negative → red (CE default).
_CLF_POS_COLOR = "#d62728"   # tab:red
_CLF_NEG_COLOR = "#1f77b4"   # tab:blue
_REG_POS_COLOR = "#1f77b4"   # tab:blue
_REG_NEG_COLOR = "#d62728"   # tab:red
# Body interval overlay colors — parity with CE matplotlib fill_betweenx at alpha 0.2.
# Classification body: positive contribution range → red alpha 0.2, negative → blue alpha 0.2.
# Regression body: positive → blue alpha 0.2, negative → red alpha 0.2.
_CLF_POS_INTERVAL = "rgba(214, 39, 40, 0.40)"   # red, alpha 0.4 — visible in extension beyond solid
_CLF_NEG_INTERVAL = "rgba(31, 119, 180, 0.40)"  # blue, alpha 0.4
_REG_POS_INTERVAL = "rgba(31, 119, 180, 0.40)"  # blue, alpha 0.4
_REG_NEG_INTERVAL = "rgba(214, 39, 40, 0.40)"   # red, alpha 0.4


def _warn_fallback(reason: str) -> None:
    message = f"Plotly factual bars fallback: {reason}"
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


def _display_value(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in value)
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            return ", ".join(_display_value(item) for item in value.ravel().tolist())
        if isinstance(value, np.generic):
            return str(value.item())
    except ImportError:  # pragma: no cover - numpy is supplied by CE
        pass
    return str(value)


def _format_number(value: Any, *, signed: bool = False) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "unavailable"
    if signed:
        return f"{numeric:+.6g}"
    return f"{numeric:.6g}"


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
    is_alternative = getattr(local_explanation, "is_alternative", None)
    if callable(is_alternative):
        return bool(is_alternative())
    if isinstance(is_alternative, bool):
        return is_alternative
    return "alternative" in type(local_explanation).__name__.lower()


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


def _resolve_rules(local_explanation: Any) -> dict[str, Any]:
    get_rules = getattr(local_explanation, "get_rules", None)
    rules = get_rules() if callable(get_rules) else getattr(local_explanation, "rules", None)
    if not isinstance(rules, Mapping):
        build_payload = getattr(local_explanation, "build_rules_payload", None)
        if callable(build_payload):
            payload = build_payload()
            rules = payload if isinstance(payload, Mapping) else getattr(payload, "rules", None)
    if not isinstance(rules, Mapping):
        raise ValueError("The explanation does not expose factual rule contributions.")
    return dict(rules)


def _compute_ranking(
    local_explanation: Any,
    rules: dict[str, Any],
    options: dict[str, Any],
) -> list[int] | None:
    """Return display-ordered indices using CE core ranking semantics.

    When sort_by is explicitly set, returns None so the caller falls back to
    _sort_items. Otherwise returns a list of original rule indices ordered from
    most important (index 0) to least important, matching CE's rank_features
    ascending-then-reversed convention.
    """
    if options.get("sort_by") is not None:
        return None

    weights = list(rules.get("weight", ()))
    n = len(weights)
    if n == 0:
        return []

    filter_top = options.get("filter_top")
    if filter_top is None:
        filter_top = n
    filter_top = min(n, max(0, int(filter_top)))
    if filter_top <= 0:
        return []

    rnk_metric = str(options.get("rnk_metric", "feature_weight"))
    rnk_weight = float(options.get("rnk_weight", 0.5))

    import numpy as np  # noqa: PLC0415 — conditional import for non-plotting code path

    fw = np.nan_to_num(
        np.array([_as_float(w) or 0.0 for w in weights]),
        nan=0.0,
        posinf=np.finfo(float).max,
        neginf=-np.finfo(float).max,
    )

    # Compute weight-interval width for tie-breaking / ensured ranking
    lows = list(rules.get("weight_low", rules.get("low", [])))
    highs = list(rules.get("weight_high", rules.get("high", [])))
    width: Any = None
    if len(lows) == n and len(highs) == n:
        with contextlib.suppress(Exception):
            low_arr = np.array([_as_float(v) or 0.0 for v in lows])
            high_arr = np.array([_as_float(v) or 0.0 for v in highs])
            width = np.nan_to_num(high_arr - low_arr, nan=0.0)

    rank_fn = getattr(local_explanation, "rank_features", None)

    if rnk_metric == "feature_weight":
        if callable(rank_fn):
            with contextlib.suppress(Exception):
                raw = rank_fn(fw, width=width, num_to_show=filter_top)
                indices = list(raw.tolist() if hasattr(raw, "tolist") else list(raw))
                return list(reversed(indices))
        # Fallback: replicate CE rank_features logic inline
        if width is not None:
            paired = list(zip(np.abs(fw), width, strict=False))
            sorted_idx = sorted(range(n), key=lambda i: (paired[i][0], paired[i][1]))
        else:
            sorted_idx = sorted(range(n), key=lambda i: float(np.abs(fw[i])))
        top_k = sorted_idx[-filter_top:]
        return list(reversed(top_k))

    # Non-feature_weight: try calculate_metrics (CE ensured/uncertainty path)
    with contextlib.suppress(Exception):
        from calibrated_explanations.utils.metrics import calculate_metrics  # noqa: PLC0415

        predict_lows = list(rules.get("predict_low", []))
        predict_highs = list(rules.get("predict_high", []))
        predict_vals = list(rules.get("predict", []))

        uncertainty_vals: list[float] = []
        for i in range(n):
            pl = _as_float(_sequence_get(predict_lows, i))
            ph = _as_float(_sequence_get(predict_highs, i))
            if pl is not None and ph is not None:
                uncertainty_vals.append(float(ph) - float(pl))
            elif width is not None and i < len(width):
                uncertainty_vals.append(float(width[i]))
            else:
                uncertainty_vals.append(0.0)

        prediction_vals = (
            [_as_float(v) or 0.0 for v in predict_vals]
            if predict_vals
            else [float(fw[i]) for i in range(n)]
        )

        ranking = calculate_metrics(
            uncertainty=uncertainty_vals,
            prediction=prediction_vals,
            w=rnk_weight,
            metric=rnk_metric,
        )
        rank_arr = np.nan_to_num(np.array(ranking, dtype=float), nan=0.0)
        if callable(rank_fn):
            raw = rank_fn(width=rank_arr, num_to_show=filter_top)
            indices = list(raw.tolist() if hasattr(raw, "tolist") else list(raw))
            return list(reversed(indices))
        sorted_idx = sorted(range(n), key=lambda i: float(rank_arr[i]))
        top_k = sorted_idx[-filter_top:]
        return list(reversed(top_k))

    # Final fallback: sort by abs weight
    sorted_idx = sorted(range(n), key=lambda i: float(np.abs(fw[i])))
    top_k = sorted_idx[-filter_top:]
    return list(reversed(top_k))


def _prediction_header(
    local_explanation: Any,
    mode_metadata: dict[str, Any],
    *,
    y_minmax: list[float] | None = None,
) -> dict[str, Any]:
    prediction = getattr(local_explanation, "prediction", None)
    if isinstance(prediction, dict):
        value = prediction.get("predict", prediction.get("prediction"))
        low = prediction.get("low", prediction.get("predict_low"))
        high = prediction.get("high", prediction.get("predict_high"))
        label = prediction.get("classes", prediction.get("class", prediction.get("label")))
    else:
        value = getattr(local_explanation, "predict", None)
        low = getattr(local_explanation, "low", None)
        high = getattr(local_explanation, "high", None)
        label = None
    p = _as_float(value)
    p_low = _as_float(low)
    p_high = _as_float(high)
    result: dict[str, Any] = {
        "value": p,
        "low": p_low,
        "high": p_high,
        "label": None if label is None else str(label),
        "mode": mode_metadata.get("mode"),
        "task": mode_metadata.get("task"),
    }

    task = mode_metadata.get("task")
    is_probabilistic = mode_metadata.get("is_probabilistic", False)
    is_regression = mode_metadata.get("is_regression", False)

    if is_probabilistic or task in ("classification",):
        # Class-label resolution in preference order:
        # 1. get_class_labels() on collection (CE canonical)
        # 2. prediction["classes"/"class"/"label"] from artifact
        # 3. threshold labels for thresholded explanations
        # 4. generic fallback
        collection = _collection_for(local_explanation)
        get_cls_fn = getattr(local_explanation, "get_class_labels", None) or getattr(
            collection, "get_class_labels", None
        )
        class_labels = None
        if callable(get_cls_fn):
            with contextlib.suppress(Exception):
                class_labels = get_cls_fn()

        # Determine predicted class for multiclass: use prediction["classes"] if present
        predicted_class = None
        if isinstance(prediction, dict):
            predicted_class = prediction.get("classes", prediction.get("class"))

        # Label priority:
        # 1. pos_caption / neg_caption on the explanation (user-set, already formatted)
        # 2. class_labels from get_class_labels(), wrapped as P(Y=…) / P(Y!=…)
        # 3. prediction["classes"] index, wrapped as P(Y=…) / P(Y!=…)
        # 4. threshold labels (keep existing format)
        # 5. generic P(Y=1) / P(Y!=1) fallback
        pos_caption = getattr(local_explanation, "pos_caption", None)
        neg_caption = getattr(local_explanation, "neg_caption", None)

        if pos_caption is not None and neg_caption is not None:
            target_label = str(pos_caption)
            complement_label = str(neg_caption)
        elif class_labels is not None and len(class_labels) >= 2:
            target_idx = 1  # binary default
            if predicted_class is not None:
                with contextlib.suppress(Exception):
                    target_idx = int(predicted_class)
            target_label = f"P(Y={class_labels[target_idx]})"
            complement_label = f"P(Y!={class_labels[target_idx]})"
        elif label is not None:
            target_label = f"P(Y={label})"
            complement_label = f"P(Y!={label})"
        else:
            is_thresholded_fn = getattr(local_explanation, "is_thresholded", None)
            threshold_val = getattr(local_explanation, "threshold", None)
            if callable(is_thresholded_fn) and is_thresholded_fn() and threshold_val is not None:
                target_label = f"P(y > {threshold_val})"
                complement_label = f"P(y <= {threshold_val})"
            else:
                target_label = "P(Y=1)"
                complement_label = "P(Y!=1)"
        bars: list[dict[str, Any]] = []
        if p is not None:
            target_bar: dict[str, Any] = {"label": target_label, "value": p}
            if p_low is not None:
                target_bar["low"] = p_low
            if p_high is not None:
                target_bar["high"] = p_high
            bars.append(target_bar)

            complement_bar: dict[str, Any] = {"label": complement_label, "value": 1.0 - p}
            if p_low is not None and p_high is not None:
                complement_bar["low"] = 1.0 - p_high
                complement_bar["high"] = 1.0 - p_low
            bars.append(complement_bar)
        result["kind"] = "probabilistic"
        result["bars"] = bars
        result["x_range"] = [0.0, 1.0]
        result["x_label"] = "Probability"
    elif is_regression or task == "regression":
        bars = []
        if p is not None:
            regression_bar: dict[str, Any] = {"label": "prediction", "value": p}
            if p_low is not None:
                regression_bar["low"] = p_low
            if p_high is not None:
                regression_bar["high"] = p_high
            bars.append(regression_bar)
        result["kind"] = "regression"
        result["bars"] = bars
        x_range: list[float] | None = None
        if y_minmax is not None:
            with contextlib.suppress(Exception):
                lo = float(y_minmax[0])
                hi = float(y_minmax[1])
                if p_low is not None:
                    lo = min(lo, float(p_low))
                if p_high is not None:
                    hi = max(hi, float(p_high))
                if lo < hi:
                    x_range = [lo, hi]
        result["x_range"] = x_range
        # Match CE core: "Prediction interval with {confidence}% confidence"
        collection = _collection_for(local_explanation)
        confidence = None
        get_conf = getattr(collection, "get_confidence", None)
        if callable(get_conf):
            with contextlib.suppress(Exception):
                confidence = get_conf()
        if confidence is not None:
            result["x_label"] = f"Prediction interval with {confidence}% confidence"
        else:
            result["x_label"] = "Prediction interval"
    else:
        result["kind"] = None
        result["bars"] = []
        result["x_range"] = None
        result["x_label"] = None

    return result


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


def _default_options(options: dict[str, Any]) -> dict[str, Any]:
    # sort_by is an explicit override; None means use CE core ranking (rnk_metric/rnk_weight)
    sort_by = options.get("sort_by")
    if sort_by is not None:
        sort_by = str(sort_by)
        if sort_by not in {"abs", "value", "interval_width", "label", "original"}:
            raise ValueError(
                "sort_by must be one of abs, value, interval_width, label, or original."
            )
    orientation = str(options.get("orientation", "horizontal"))
    if orientation != "horizontal":
        raise ValueError("plotly.local.factual_bars supports orientation='horizontal' only.")
    hover_detail = str(options.get("hover_detail", "compact"))
    if hover_detail not in {"compact", "full"}:
        raise ValueError("hover_detail must be compact or full.")
    filter_top = options.get("filter_top")
    rnk_metric = str(options.get("rnk_metric", "feature_weight"))
    if rnk_metric == "uncertainty":
        rnk_metric = "ensured"
        rnk_weight = 1.0
    else:
        rnk_weight = float(options.get("rnk_weight", 0.5))
    return {
        "filter_top": None if filter_top is None else int(filter_top),
        "sort_by": sort_by,
        "rnk_metric": rnk_metric,
        "rnk_weight": rnk_weight,
        "show_uncertainty": bool(
            options.get("show_uncertainty", bool(options.get("uncertainty", False)))
        ),
        "hover_uncertainty": bool(options.get("hover_uncertainty", True)),
        "show_prediction_header": bool(options.get("show_prediction_header", True)),
        "hover_detail": hover_detail,
        "orientation": orientation,
        "include_missing_interval_items": bool(
            options.get("include_missing_interval_items", True)
        ),
    }


def _direction_for(contribution: float) -> str:
    return "positive" if contribution >= 0.0 else "negative"


def _decimal_places_in_rule(rule_str: str) -> int:
    """Return the maximum number of decimal places used in any numeric threshold in a rule."""
    parts = re.findall(r"\d+\.(\d+)", str(rule_str))
    return max((len(p) for p in parts), default=0)


def _build_hover(item: dict[str, Any], prediction: dict[str, Any], options: dict[str, Any]) -> str:
    lines = [
        f"Rule: {_display_value(item.get('rule'))}",
    ]
    if item.get("feature_name") is not None:
        lines.append(f"Feature: {_display_value(item.get('feature_name'))}")
    if item.get("feature_index") is not None:
        lines.append(f"Feature index: {_display_value(item.get('feature_index'))}")
    if item.get("instance_value") is not None:
        lines.append(f"Current value: {_display_value(item.get('instance_value'))}")
    lines.append(f"Contribution: {_format_number(item.get('contribution'), signed=True)}")
    if options.get("hover_uncertainty", True):
        low = item.get("contribution_low")
        high = item.get("contribution_high")
        if low is None or high is None:
            lines.append("Contribution interval: unavailable")
            if options.get("hover_detail") == "full":
                lines.append("Interval width: unavailable")
                lines.append("Crosses zero: unavailable")
        else:
            lines.append(
                "Contribution interval: "
                f"[{_format_number(low)}, {_format_number(high)}]"
            )
            lines.append(f"Interval width: {_format_number(item.get('interval_width'))}")
            lines.append(f"Crosses zero: {'yes' if item.get('crosses_zero') else 'no'}")
    if prediction.get("value") is not None:
        lines.append(f"Prediction: {_format_number(prediction.get('value'))}")
    if prediction.get("low") is not None and prediction.get("high") is not None:
        lines.append(
            "Prediction interval: "
            f"[{_format_number(prediction.get('low'))}, {_format_number(prediction.get('high'))}]"
        )
    if prediction.get("task") is not None:
        lines.append(f"Task: {prediction.get('task')}")
    if prediction.get("mode") is not None:
        lines.append(f"Mode: {prediction.get('mode')}")
    return "<br>".join(lines)


def _extract_items(
    local_explanation: Any,
    prediction: dict[str, Any],
    options: dict[str, Any],
    *,
    indices: list[int] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Extract rule items, optionally restricted to the given original-index list."""
    rules = _resolve_rules(local_explanation)
    weights = list(rules.get("weight", ()))
    lows = list(rules.get("weight_low", rules.get("low", ())))
    highs = list(rules.get("weight_high", rules.get("high", ())))
    labels = list(rules.get("rule", ()))
    features = list(rules.get("feature", ()))
    values = list(rules.get("value", ()))
    feature_values = list(rules.get("feature_value", ()))
    collection = _collection_for(local_explanation)
    include_missing = bool(options.get("include_missing_interval_items", True))

    # Determine which indices to visit, in display order
    index_iter = indices if indices is not None else list(range(len(weights)))

    items: list[dict[str, Any]] = []
    missing_intervals = 0

    for original_index in index_iter:
        raw_weight = _sequence_get(weights, original_index)
        contribution = _as_float(raw_weight)
        if contribution is None:
            continue
        low = _as_float(_sequence_get(lows, original_index))
        high = _as_float(_sequence_get(highs, original_index))
        if low is None or high is None:
            missing_intervals += 1
            if not include_missing:
                continue
            width = None
            crosses_zero = None
        else:
            width = high - low
            crosses_zero = low <= 0.0 <= high
        feature = _sequence_get(features, original_index)
        item = {
            "id": f"rule-{original_index}",
            "rank": len(items),
            "feature_index": feature,
            "feature_name": _feature_name(collection, feature),
            "rule": str(_sequence_get(labels, original_index, f"rule {original_index}")),
            "instance_value": _sequence_get(
                feature_values,
                original_index,
                _sequence_get(values, original_index),
            ),
            "contribution": contribution,
            "contribution_low": low,
            "contribution_high": high,
            "interval_width": width,
            "crosses_zero": crosses_zero,
            "direction": _direction_for(contribution),
            "hover": "",
            "metadata": {"original_index": original_index},
        }
        item["hover"] = _build_hover(item, prediction, options)
        items.append(item)
    return items, missing_intervals


def _sort_items(items: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by == "original":
        return list(items)
    if sort_by == "abs":
        return sorted(items, key=lambda item: (-abs(item["contribution"]), item["rank"]))
    if sort_by == "value":
        return sorted(items, key=lambda item: (-item["contribution"], item["rank"]))
    if sort_by == "interval_width":
        return sorted(
            items,
            key=lambda item: (
                -(item["interval_width"] if item["interval_width"] is not None else -1.0),
                item["rank"],
            ),
        )
    return sorted(items, key=lambda item: (str(item.get("rule") or ""), item["rank"]))


class LocalFactualBarsPlotBuilder(PlotBuilder):
    """Build a Plotly artifact for local factual contribution bars."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
        "data_modalities": ("tabular",),
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
            raise ValueError("plotly.local.factual_bars supports factual local explanations only.")

        options = _default_options(dict(context.options))
        local_explanation = _select_local_explanation(
            context.explanation,
            context.options.get("instance_index"),
        )
        if _is_alternative_explanation(local_explanation):
            raise ValueError("plotly.local.factual_bars does not support alternative explanations.")

        # Guard: one-sided explanations have no contribution intervals.
        # Match CE core behaviour: raise Warning (same class as core does).
        # Note: Warning is a subclass of Exception, so contextlib.suppress(Exception) must NOT
        # wrap the raise — only the is_one_sided() call gets suppressed on error.
        if options["show_uncertainty"]:
            is_one_sided_fn = getattr(local_explanation, "is_one_sided", None)
            if callable(is_one_sided_fn):
                _is_one_sided = False
                with contextlib.suppress(Exception):
                    _is_one_sided = bool(is_one_sided_fn())
                if _is_one_sided:
                    raise Warning(
                        "Interval plot is not supported for one-sided explanations."
                    )

        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        collection = _collection_for(local_explanation)
        is_regression = bool(mode_metadata.get("is_regression", False))
        y_minmax: list[float] | None = None
        if is_regression:
            y_minmax_raw = getattr(collection, "y_minmax", None)
            if y_minmax_raw is not None:
                with contextlib.suppress(Exception):
                    y_minmax = [float(y_minmax_raw[0]), float(y_minmax_raw[1])]
            if y_minmax is None:
                for _cal_attr in ("y_cal", "y"):
                    _y = getattr(collection, _cal_attr, None)
                    if _y is not None:
                        with contextlib.suppress(Exception):
                            _arr = list(_y)
                            if _arr:
                                y_minmax = [float(min(_arr)), float(max(_arr))]
                                break
        prediction = _prediction_header(local_explanation, mode_metadata, y_minmax=y_minmax)

        # Determine display order using CE core ranking, unless sort_by is explicit
        rules = _resolve_rules(local_explanation)
        ranking_indices = _compute_ranking(local_explanation, rules, options)

        if ranking_indices is not None:
            # CE-ranked path: items are already ordered by _compute_ranking
            items, missing_intervals = _extract_items(
                local_explanation, prediction, options, indices=ranking_indices
            )
        else:
            # sort_by explicit override path
            items, missing_intervals = _extract_items(local_explanation, prediction, options)
            sort_by = str(options["sort_by"])
            items = _sort_items(items, sort_by)
            filter_top = options["filter_top"]
            if filter_top is not None:
                items = items[: int(filter_top)]

        if not items:
            raise ValueError("No factual rule contributions were available for plotting.")

        for rank, item in enumerate(items):
            item["rank"] = rank

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "prediction": prediction,
            "items": items,
            "axis_metadata": {
                "x_label": "Feature weights",
                "y_label": "Rules",
                "zero_line": True,
            },
            "options_used": {
                "filter_top": options["filter_top"],
                "sort_by": options["sort_by"],
                "rnk_metric": options["rnk_metric"],
                "rnk_weight": options["rnk_weight"],
                "show_uncertainty": options["show_uncertainty"],
                "hover_uncertainty": options["hover_uncertainty"],
                "show_prediction_header": options["show_prediction_header"],
                "hover_detail": options["hover_detail"],
            },
            "metadata": {
                "num_items": len(items),
                "num_missing_intervals": missing_intervals,
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


def _title_for(artifact: PlotArtifact, options: dict[str, Any]) -> str:
    # Default to no title for strict parity with CE legacy/PlotSpec behaviour.
    # CE core plots do not set a visible figure title; they use axis labels only.
    return ""


def _interval_color_for(
    direction: str,
    *,
    is_classification: bool,
    crossing_side: str | None = None,
) -> str:
    """Return the legacy-parity interval overlay color for a contribution bar.

    For crossing-zero rules, crossing_side is 'negative' or 'positive'.
    For non-crossing rules, direction determines the color.
    Classification: positive → red alpha 0.2, negative → blue alpha 0.2.
    Regression: positive → blue alpha 0.2, negative → red alpha 0.2.
    """
    side = crossing_side if crossing_side is not None else direction
    if is_classification:
        return _CLF_POS_INTERVAL if side == "positive" else _CLF_NEG_INTERVAL
    return _REG_POS_INTERVAL if side == "positive" else _REG_NEG_INTERVAL


def _compute_body_xrange(
    items: list[dict[str, Any]],
    render_options: dict[str, Any],
    prediction: dict[str, Any],
    *,
    is_dual_header: bool,
) -> list[float] | None:
    """Derive body x-axis range from all body primitives, mirroring PlotSpec adapter logic."""
    show_uncertainty = bool(render_options.get("show_uncertainty", False))
    vals: list[float] = [0.0]

    for item in items:
        contribution = _as_float(item.get("contribution"))
        if contribution is None:
            continue
        if show_uncertainty and item.get("crosses_zero"):
            vals.append(0.0)
        else:
            vals.append(contribution)
        if show_uncertainty:
            low = _as_float(item.get("contribution_low"))
            high = _as_float(item.get("contribution_high"))
            if low is not None:
                vals.append(low)
            if high is not None:
                vals.append(high)

    if is_dual_header and show_uncertainty:
        p_val = _as_float(prediction.get("value"))
        p_lo = _as_float(prediction.get("low"))
        p_hi = _as_float(prediction.get("high"))
        if p_val is not None and p_lo is not None and p_hi is not None:
            vals.append(p_lo - p_val)
            vals.append(p_hi - p_val)

    if not vals:
        return None

    x_min = min(vals)
    x_max = max(vals)

    if x_min == x_max:
        x_min -= 0.1
        x_max += 0.1

    if is_dual_header:
        span = x_max - x_min
        padding = span * 0.05
        x_min -= padding
        x_max += padding

    return [x_min, x_max]


def _add_contribution_traces(
    fig: Any,
    items: list[dict[str, Any]],
    labels: list[str],
    values: list[float],
    colors: list[str],
    hover_text: list[str],
    render_options: dict[str, Any],
    *,
    row: int | None = None,
    col: int | None = None,
) -> None:
    """Add the main contribution bar trace and optional uncertainty overlay."""
    import plotly.graph_objects as go  # noqa: PLC0415

    add_kwargs: dict[str, Any] = {}
    if row is not None:
        add_kwargs["row"] = row
        add_kwargs["col"] = col

    show_uncertainty = bool(render_options.get("show_uncertainty", False))
    is_classification = bool(render_options.get("is_classification", False))

    # Clip solid bar to the inner edge of the uncertainty interval so the band
    # [weight_low, weight_high] is fully visible with no solid bar overlapping it.
    # Positive: solid [0, weight_low]; uncertainty [weight_low, weight_high].
    # Negative: solid [0, weight_high]; uncertainty [weight_low, weight_high].
    # Crossing-zero intervals suppress the solid bar entirely (solid = 0).
    if show_uncertainty:
        display_values = []
        for item, v in zip(items, values, strict=False):
            if item.get("crosses_zero") is True:
                display_values.append(0.0)
            else:
                low = item.get("contribution_low")
                high = item.get("contribution_high")
                if low is not None and high is not None:
                    direction = item.get("direction", "positive")
                    if direction == "positive":
                        display_values.append(max(0.0, float(low)))
                    else:
                        display_values.append(min(0.0, float(high)))
                else:
                    display_values.append(v)
    else:
        display_values = values

    if show_uncertainty:
        # Uncertainty bands are added FIRST so the solid bar renders on top (matching
        # PlotSpec's fill_betweenx-then-barh paint order). The extension region beyond
        # the solid bar shows the translucent band; the overlap region is covered.
        # Build per-entry list of (y_label, base, width, color, hover).
        # For crossing-zero intervals, emit two entries (negative and positive sides).
        bar_entries: list[tuple[str, float, float, str, str]] = []

        for label, item in zip(labels, items, strict=False):
            low = item.get("contribution_low")
            high = item.get("contribution_high")
            if low is None or high is None:
                continue
            low_f, high_f = float(low), float(high)
            direction = item.get("direction", "positive")
            hover = str(item.get("hover", ""))
            if item.get("crosses_zero") and low_f < 0.0 < high_f:
                neg_color = _interval_color_for(
                    direction, is_classification=is_classification, crossing_side="negative"
                )
                pos_color = _interval_color_for(
                    direction, is_classification=is_classification, crossing_side="positive"
                )
                bar_entries.append((label, low_f, -low_f, neg_color, hover))
                bar_entries.append((label, 0.0, high_f, pos_color, hover))
            else:
                interval_color = _interval_color_for(
                    direction, is_classification=is_classification
                )
                bar_entries.append((label, low_f, high_f - low_f, interval_color, hover))

        color_groups: dict[str, list[tuple[str, float, float, str]]] = {}
        for y_label, base, width, color, hover in bar_entries:
            if color not in color_groups:
                color_groups[color] = []
            color_groups[color].append((y_label, base, width, hover))

        for color, entries in color_groups.items():
            fig.add_trace(
                go.Bar(
                    x=[e[2] for e in entries],
                    y=[e[0] for e in entries],
                    base=[e[1] for e in entries],
                    orientation="h",
                    marker={"color": color},
                    hovertext=[e[3] for e in entries],
                    hovertemplate="%{hovertext}<extra></extra>",
                    showlegend=False,
                    name="contribution interval",
                ),
                **add_kwargs,
            )

    # Solid contribution bar — added after uncertainty so it renders on top.
    # No explicit width: Plotly bargap default (0.2) gives 80% fill, matching
    # matplotlib's default barh height=0.8 for visual parity across all panels.
    fig.add_trace(
        go.Bar(
            x=display_values,
            y=labels,
            orientation="h",
            marker={"color": colors},
            text=None,
            hovertext=hover_text,
            hovertemplate="%{hovertext}<extra></extra>",
            name="contribution",
        ),
        **add_kwargs,
    )


def _add_prediction_header_traces(
    fig: Any,
    prediction: dict[str, Any],
    *,
    row: int,
    col: int,
    color: str | None = None,
) -> None:
    """Add prediction probability/regression bars to the header subplot row.

    Probabilistic header: three-part per bar — solid 0→low, translucent low→high,
    vertical marker at predict.

    Regression header: interval bar low→high, vertical marker at predict.
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    bars = list(prediction.get("bars", ()) or [])
    kind = prediction.get("kind")
    # Regression header uses red to match CE legacy (fill_betweenx color="r").
    # Probabilistic header uses teal for probability bars.
    _default_color = "#2a9d8f" if kind == "probabilistic" else "#d62728"
    bar_color = color if color is not None else _default_color

    for bar in bars:
        p_val = _as_float(bar.get("value"))
        p_low = _as_float(bar.get("low"))
        p_high = _as_float(bar.get("high"))
        bar_label = str(bar.get("label", "prediction"))
        if p_val is None:
            continue

        hover_parts = [f"{bar_label}: {_format_number(p_val)}"]
        if p_low is not None and p_high is not None:
            hover_parts.append(
                f"Interval: [{_format_number(p_low)}, {_format_number(p_high)}]"
            )
        else:
            hover_parts.append("Interval: unavailable")
        hover = "<br>".join(hover_parts)

        if kind == "probabilistic":
            # ── Solid portion: 0 to p_low (the certain minimum) ──────────────
            solid_width = float(p_low) if p_low is not None else 0.0
            if solid_width > 0.0:
                fig.add_trace(
                    go.Bar(
                        x=[solid_width],
                        y=[bar_label],
                        base=[0.0],
                        orientation="h",
                        marker={"color": bar_color},
                        hovertext=[hover],
                        hovertemplate="%{hovertext}<extra></extra>",
                        showlegend=False,
                        name=f"solid: {bar_label}",
                    ),
                    row=row,
                    col=col,
                )

            # ── Translucent interval: p_low to p_high ─────────────────────────
            if p_low is not None and p_high is not None and p_high > p_low:
                fig.add_trace(
                    go.Bar(
                        x=[float(p_high) - float(p_low)],
                        y=[bar_label],
                        base=[float(p_low)],
                        orientation="h",
                        marker={"color": bar_color, "opacity": 0.35},
                        hovertext=[hover],
                        hovertemplate="%{hovertext}<extra></extra>",
                        showlegend=False,
                        name=f"interval: {bar_label}",
                    ),
                    row=row,
                    col=col,
                )
            elif p_low is None or p_high is None:
                # No interval — fall back to full bar from 0 to p_val
                fig.add_trace(
                    go.Bar(
                        x=[max(0.0, float(p_val))],
                        y=[bar_label],
                        base=[0.0],
                        orientation="h",
                        marker={"color": bar_color},
                        hovertext=[hover],
                        hovertemplate="%{hovertext}<extra></extra>",
                        showlegend=False,
                        name=f"prediction: {bar_label}",
                    ),
                    row=row,
                    col=col,
                )

        else:
            # ── Regression: interval bar from p_low to p_high ─────────────────
            if p_low is not None and p_high is not None:
                fig.add_trace(
                    go.Bar(
                        x=[float(p_high) - float(p_low)],
                        y=[bar_label],
                        base=[float(p_low)],
                        orientation="h",
                        marker={"color": bar_color, "opacity": 0.5},
                        hovertext=[hover],
                        hovertemplate="%{hovertext}<extra></extra>",
                        showlegend=False,
                        name=f"prediction: {bar_label}",
                    ),
                    row=row,
                    col=col,
                )

        # ── Prediction point marker at p_val (all kinds) ──────────────────────
        fig.add_trace(
            go.Scatter(
                x=[float(p_val)],
                y=[bar_label],
                mode="markers",
                marker={
                    "symbol": "line-ns-open",
                    "size": 12,
                    "color": bar_color,
                    "line": {"width": 2.5, "color": bar_color},
                },
                hovertext=[hover],
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
                name=f"marker: {bar_label}",
            ),
            row=row,
            col=col,
        )


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    """Build Plotly figure for factual contribution bars.

    When show_prediction_header=True and prediction bars are available, renders a
    two-row subplot with probability/regression bars above the contribution bars.
    """
    import plotly.graph_objects as go

    render_options = dict(artifact.get("options_used", {}) or {})
    render_options.update(options)
    items = list(artifact.get("items", ()))
    labels = [str(item.get("rule") or item.get("feature_name") or item.get("id")) for item in items]
    values = [float(item.get("contribution", 0.0)) for item in items]
    hover_text = [str(item.get("hover") or "") for item in items]

    show_prediction_header = bool(render_options.get("show_prediction_header", True))
    show_y_labels = bool(render_options.get("show_y_labels", True))
    # show_rule_labels: controls the left-side rule-condition tick labels on the primary y-axis.
    # Defaults to show_y_labels so that show_y_labels=False still hides everything (backward compat).
    # Can be set independently to hide just the rule text while keeping instance values visible.
    show_rule_labels = bool(render_options.get("show_rule_labels", show_y_labels))
    prediction = dict(artifact.get("prediction", {}) or {})
    is_classification = prediction.get("kind") == "probabilistic"
    render_options["is_classification"] = is_classification

    # Task-specific body bar colors: classification pos=red/neg=blue, regression pos=blue/neg=red
    if is_classification:
        colors = [
            _CLF_POS_COLOR if item.get("direction") == "positive" else _CLF_NEG_COLOR
            for item in items
        ]
        header_bar_colors = [_CLF_POS_COLOR, _CLF_NEG_COLOR]
    else:
        colors = [
            _REG_POS_COLOR if item.get("direction") == "positive" else _REG_NEG_COLOR
            for item in items
        ]
        # Regression header uses red to match CE legacy fill_betweenx color="r"
        header_bar_colors = ["#d62728"]

    header_bars = list(prediction.get("bars", ()) or []) if show_prediction_header else []

    axis_meta = dict(artifact.get("axis_metadata", {}) or {})
    x_label_contribution = axis_meta.get("x_label", "Feature weights")
    y_label_contribution = axis_meta.get("y_label", "Rules")

    # Right-axis instance values: use str() for parity with CE legacy y-axis labels
    instance_values = [_display_value(item.get("instance_value")) for item in items]

    if show_prediction_header and header_bars:
        from plotly.subplots import make_subplots  # noqa: PLC0415

        x_range = prediction.get("x_range")
        header_x_label = prediction.get("x_label") or ""
        n_header = len(header_bars)
        n_body = len(items)
        # Equal pixel height per category across both subplots: allocate header rows
        # proportionally so each category (header and body) gets the same row height.
        header_fraction = n_header / (n_header + n_body)
        row_heights = [header_fraction, 1.0 - header_fraction]

        fig = make_subplots(
            rows=2,
            cols=1,
            row_heights=row_heights,
            shared_xaxes=False,
            vertical_spacing=0.14,
        )

        # All header bars in row 1, each with its task-specific color
        for bar, hdr_color in zip(header_bars, header_bar_colors, strict=False):
            _add_prediction_header_traces(
                fig, {**prediction, "bars": [bar]}, row=1, col=1, color=hdr_color
            )

        _add_contribution_traces(
            fig, items, labels, values, colors, hover_text, render_options, row=2, col=1
        )

        # Base prediction uncertainty band in contribution space (alpha matches CE's 0.20)
        if render_options.get("show_uncertainty"):
            _p_val = _as_float(prediction.get("value"))
            _p_lo = _as_float(prediction.get("low"))
            _p_hi = _as_float(prediction.get("high"))
            if _p_val is not None and _p_lo is not None and _p_hi is not None:
                _band_lo = _p_lo - _p_val
                _band_hi = _p_hi - _p_val
                if _band_lo < _band_hi:
                    fig.add_vrect(
                        x0=_band_lo, x1=_band_hi,
                        fillcolor="rgba(0,0,0,0.20)",
                        layer="below", line_width=0,
                        row=2, col=1,  # type: ignore[arg-type]
                    )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333", row=2, col=1)  # type: ignore[arg-type]

        # Extra top margin: header x-axis (ticks + title) is placed at the figure top.
        # Left adapts to whether rule-condition labels are shown; right to instance-value axis.
        _margin = {
            "l": 5 if show_rule_labels else 10,
            "r": 110 if show_y_labels else 10,
            "t": 64,
            "b": 48,
        }
        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            margin=_margin,
            showlegend=False,
            barmode="overlay",
            autosize=True,
        )
        if x_range is not None:
            fig.update_xaxes(range=x_range, row=1, col=1)
        # Place the header x-axis (ticks + title) at the TOP of the header panel so
        # it never drifts into the body subplot area below.
        fig.update_xaxes(side="top", row=1, col=1)
        if header_x_label:
            fig.update_xaxes(title_text=header_x_label, row=1, col=1)
        fig.update_yaxes(autorange="reversed", row=1, col=1)
        fig.update_xaxes(title_text=x_label_contribution, row=2, col=1)
        fig.update_yaxes(title_text=y_label_contribution, automargin=True, row=2, col=1)
        fig.update_yaxes(autorange="reversed", row=2, col=1)
        if not show_rule_labels:
            fig.update_yaxes(showticklabels=False, row=2, col=1)
        body_range = _compute_body_xrange(items, render_options, prediction, is_dual_header=True)
        if body_range is not None:
            fig.update_xaxes(range=body_range, row=2, col=1)
        if show_y_labels:
            # Instance values on right via secondary y-axis overlaying body row (yaxis2).
            # Plotly maps categorical labels to integer indices 0..n-1; the reversed primary
            # places index 0 at the top. yaxis3 uses the same numeric range reversed.
            _n_body = len(labels)
            fig.update_layout(
                yaxis3={
                    "overlaying": "y2",
                    "side": "right",
                    "tickmode": "array",
                    "tickvals": list(range(_n_body)),
                    "ticktext": instance_values,
                    "title": {"text": "Instance values", "font": {"size": 11}},
                    "range": [_n_body - 0.5, -0.5],
                    "showgrid": False,
                    "zeroline": False,
                    "showline": False,
                    "ticks": "",
                }
            )
    else:
        fig = go.Figure()
        _add_contribution_traces(fig, items, labels, values, colors, hover_text, render_options)

        # Base prediction uncertainty band in contribution space (alpha matches CE's 0.20)
        if render_options.get("show_uncertainty"):
            _p_val = _as_float(prediction.get("value"))
            _p_lo = _as_float(prediction.get("low"))
            _p_hi = _as_float(prediction.get("high"))
            if _p_val is not None and _p_lo is not None and _p_hi is not None:
                _band_lo = _p_lo - _p_val
                _band_hi = _p_hi - _p_val
                if _band_lo < _band_hi:
                    fig.add_vrect(
                        x0=_band_lo, x1=_band_hi,
                        fillcolor="rgba(0,0,0,0.20)",
                        layer="below", line_width=0,
                    )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333")
        _margin = {
            "l": 5 if show_rule_labels else 10,
            "r": 110 if show_y_labels else 10,
            "t": 48,
            "b": 48,
        }
        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            xaxis_title=x_label_contribution,
            yaxis_title=y_label_contribution,
            yaxis={"autorange": "reversed", "showticklabels": show_rule_labels, "automargin": True},
            margin=_margin,
            showlegend=False,
            barmode="overlay",
            autosize=True,
        )
        body_range = _compute_body_xrange(items, render_options, prediction, is_dual_header=False)
        if body_range is not None:
            fig.update_xaxes(range=body_range)
        if show_y_labels:
            # Instance values on right via secondary y-axis overlaying primary body axis.
            _n_body = len(labels)
            fig.update_layout(
                yaxis2={
                    "overlaying": "y",
                    "side": "right",
                    "tickmode": "array",
                    "tickvals": list(range(_n_body)),
                    "ticktext": instance_values,
                    "title": {"text": "Instance values", "font": {"size": 11}},
                    "range": [_n_body - 0.5, -0.5],
                    "showgrid": False,
                    "zeroline": False,
                    "showline": False,
                    "ticks": "",
                }
            )
    return fig


class LocalFactualBarsPlotRenderer(PlotRenderer):
    """Render factual bar artifacts as Plotly horizontal bar charts."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": ARTIFACT_VERSION,
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
            figure = build_figure(artifact, dict(context.options))
        except ImportError as exc:
            raise RuntimeError(
                "Plotly is required to render plotly.local.factual_bars. "
                "Install this package with the [plotly] extra."
            ) from exc

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


__all__ = [
    "STYLE_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "ARTIFACT_VERSION",
    "LocalFactualBarsPlotBuilder",
    "LocalFactualBarsPlotRenderer",
    "build_figure",
    "_compute_body_xrange",
]
