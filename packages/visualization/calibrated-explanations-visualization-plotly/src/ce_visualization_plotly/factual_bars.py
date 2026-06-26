from __future__ import annotations

import contextlib
import logging
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

STYLE_ID = "plotly.local.factual_bars"
BUILDER_ID = "official.visualization.plotly.local.factual_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.factual_bars.renderer"
ARTIFACT_VERSION = "0.1.0"

_LOGGER = logging.getLogger(__name__)
_POSITIVE_COLOR = "#2a9d8f"
_NEGATIVE_COLOR = "#b84a51"
_INTERVAL_COLOR = "rgba(45, 55, 72, 0.45)"
_INTERVAL_NEG_COLOR = "rgba(184, 74, 81, 0.65)"
_INTERVAL_POS_COLOR = "rgba(42, 157, 143, 0.65)"


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
    rules = getattr(local_explanation, "rules", None)
    if not isinstance(rules, dict):
        build_payload = getattr(local_explanation, "build_rules_payload", None)
        if callable(build_payload):
            payload = build_payload()
            rules = payload if isinstance(payload, dict) else getattr(payload, "rules", None)
    if not isinstance(rules, dict):
        get_rules = getattr(local_explanation, "get_rules", None)
        rules = get_rules() if callable(get_rules) else None
    if not isinstance(rules, dict):
        raise ValueError("The explanation does not expose factual rule contributions.")
    return rules


def _prediction_header(local_explanation: Any, mode_metadata: dict[str, Any]) -> dict[str, Any]:
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

    # Additive per-bar info for the visual header renderer.
    task = mode_metadata.get("task")
    is_probabilistic = mode_metadata.get("is_probabilistic", False)
    is_regression = mode_metadata.get("is_regression", False)

    if is_probabilistic or task in ("classification",):
        # Attempt class-label resolution in preference order:
        # 1. CE collection-level get_class_labels()
        # 2. prediction["classes"/"class"/"label"] from the artifact
        # 3. threshold labels if explanation is thresholded
        # 4. generic fallback
        collection = _collection_for(local_explanation)
        get_cls_fn = getattr(local_explanation, "get_class_labels", None) or getattr(
            collection, "get_class_labels", None
        )
        class_labels = None
        if callable(get_cls_fn):
            with contextlib.suppress(Exception):
                class_labels = get_cls_fn()
        if class_labels is not None and len(class_labels) >= 2:
            target_label = str(class_labels[1])
            complement_label = str(class_labels[0])
        elif label is not None:
            target_label = str(label)
            complement_label = "complement"
        else:
            is_thresholded_fn = getattr(local_explanation, "is_thresholded", None)
            threshold_val = getattr(local_explanation, "threshold", None)
            if callable(is_thresholded_fn) and is_thresholded_fn() and threshold_val is not None:
                target_label = f"P(y > {threshold_val})"
                complement_label = f"P(y ≤ {threshold_val})"
            else:
                target_label = "class 1"
                complement_label = "class 0"
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
                # Complement interval: [1-high, 1-low] — do not mutate stored values
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
        result["x_range"] = None
        result["x_label"] = "Predicted value"
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
    sort_by = str(options.get("sort_by", "original"))
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
    return {
        "filter_top": None if filter_top is None else int(filter_top),
        "sort_by": sort_by,
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
) -> tuple[list[dict[str, Any]], int]:
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
    items: list[dict[str, Any]] = []
    missing_intervals = 0

    for original_index, raw_weight in enumerate(weights):
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
            "rank": original_index,
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

        # Guard: one-sided explanations have no contribution intervals
        if options["show_uncertainty"]:
            is_one_sided_fn = getattr(local_explanation, "is_one_sided", None)
            if callable(is_one_sided_fn):
                with contextlib.suppress(Exception):
                    if is_one_sided_fn():
                        warnings.warn(
                            "Interval plot is not supported for one-sided explanations; "
                            "show_uncertainty disabled.",
                            UserWarning,
                            stacklevel=2,
                        )
                        options["show_uncertainty"] = False

        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        prediction = _prediction_header(local_explanation, mode_metadata)
        items, missing_intervals = _extract_items(local_explanation, prediction, options)
        if not items:
            raise ValueError("No factual rule contributions were available for plotting.")

        sorted_items = _sort_items(items, str(options["sort_by"]))
        if options["filter_top"] is not None:
            sorted_items = sorted_items[: int(options["filter_top"])]
        for rank, item in enumerate(sorted_items):
            item["rank"] = rank

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "prediction": prediction,
            "items": sorted_items,
            "axis_metadata": {
                "x_label": "Signed local contribution",
                "y_label": "Factual rule / feature",
                "zero_line": True,
            },
            "options_used": {
                "filter_top": options["filter_top"],
                "sort_by": options["sort_by"],
                "show_uncertainty": options["show_uncertainty"],
                "hover_uncertainty": options["hover_uncertainty"],
                "show_prediction_header": options["show_prediction_header"],
                "hover_detail": options["hover_detail"],
            },
            "metadata": {
                "num_items": len(sorted_items),
                "num_missing_intervals": missing_intervals,
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


def _title_for(artifact: PlotArtifact, options: dict[str, Any]) -> str:
    if not bool(options.get("show_prediction_header", True)):
        return "Local factual contributions"
    prediction = dict(artifact.get("prediction", {}) or {})
    value = _format_number(prediction.get("value"))
    title = f"Local factual contributions - prediction {value}"
    if prediction.get("low") is not None and prediction.get("high") is not None:
        title += (
            f" [{_format_number(prediction.get('low'))}, "
            f"{_format_number(prediction.get('high'))}]"
        )
    return title


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

    # Suppress the solid bar for rules whose interval crosses zero (uncertainty=True only)
    if show_uncertainty:
        display_values = [
            0.0 if item.get("crosses_zero") is True else v
            for item, v in zip(items, values, strict=False)
        ]
    else:
        display_values = values

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
    if show_uncertainty:
        is_classification = bool(render_options.get("is_classification", False))
        x_neutral: list[float | None] = []
        y_neutral: list[str | None] = []
        x_neg: list[float | None] = []
        y_neg: list[str | None] = []
        x_pos: list[float | None] = []
        y_pos: list[str | None] = []
        for label, item in zip(labels, items, strict=False):
            low = item.get("contribution_low")
            high = item.get("contribution_high")
            if low is None or high is None:
                continue
            low_f, high_f = float(low), float(high)
            if is_classification and item.get("crosses_zero") and low_f < 0.0 < high_f:
                # Sign-split: negative half in red, positive half in teal
                x_neg.extend([low_f, 0.0, None])
                y_neg.extend([label, label, None])
                x_pos.extend([0.0, high_f, None])
                y_pos.extend([label, label, None])
            else:
                x_neutral.extend([low_f, high_f, None])
                y_neutral.extend([label, label, None])
        if x_neutral:
            fig.add_trace(
                go.Scatter(
                    x=x_neutral, y=y_neutral, mode="lines",
                    line={"color": _INTERVAL_COLOR, "width": 5},
                    hoverinfo="skip", showlegend=False, name="contribution interval",
                ),
                **add_kwargs,
            )
        if x_neg:
            fig.add_trace(
                go.Scatter(
                    x=x_neg, y=y_neg, mode="lines",
                    line={"color": _INTERVAL_NEG_COLOR, "width": 5},
                    hoverinfo="skip", showlegend=False, name="negative interval",
                ),
                **add_kwargs,
            )
        if x_pos:
            fig.add_trace(
                go.Scatter(
                    x=x_pos, y=y_pos, mode="lines",
                    line={"color": _INTERVAL_POS_COLOR, "width": 5},
                    hoverinfo="skip", showlegend=False, name="positive interval",
                ),
                **add_kwargs,
            )


def _add_prediction_header_traces(
    fig: Any,
    prediction: dict[str, Any],
    *,
    row: int,
    col: int,
) -> None:
    """Add prediction probability/regression bars to the header subplot row.

    Probabilistic header: three-part per bar — solid 0→low, translucent low→high,
    vertical marker at predict.

    Regression header: interval bar low→high, vertical marker at predict.
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    bars = list(prediction.get("bars", ()) or [])
    kind = prediction.get("kind")
    color = "#2a9d8f" if kind == "probabilistic" else "#5b8dd9"

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
                        marker={"color": color},
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
                        marker={"color": color, "opacity": 0.35},
                        hoverinfo="skip",
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
                        marker={"color": color},
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
                        marker={"color": color, "opacity": 0.5},
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
                    "color": color,
                    "line": {"width": 2.5, "color": color},
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
    colors = [
        _POSITIVE_COLOR if item.get("direction") == "positive" else _NEGATIVE_COLOR
        for item in items
    ]
    hover_text = [str(item.get("hover") or "") for item in items]

    show_prediction_header = bool(render_options.get("show_prediction_header", True))
    prediction = dict(artifact.get("prediction", {}) or {})
    header_bars = list(prediction.get("bars", ()) or []) if show_prediction_header else []
    render_options["is_classification"] = prediction.get("kind") == "probabilistic"

    axis_meta = dict(artifact.get("axis_metadata", {}) or {})
    x_label_contribution = axis_meta.get("x_label", "Signed local contribution")
    y_label_contribution = axis_meta.get("y_label", "Factual rule / feature")

    # Right-axis instance values (displayed as paper-anchored annotations)
    instance_values = [_display_value(item.get("instance_value")) for item in items]

    if show_prediction_header and header_bars:
        from plotly.subplots import make_subplots  # noqa: PLC0415

        x_range = prediction.get("x_range")
        header_x_label = prediction.get("x_label") or ""
        n_header = len(header_bars)
        row_heights = [max(0.12, 0.10 * n_header), 1.0 - max(0.12, 0.10 * n_header)]

        fig = make_subplots(
            rows=2,
            cols=1,
            row_heights=row_heights,
            shared_xaxes=False,
            vertical_spacing=0.08,
            subplot_titles=["Prediction", "Local factual contributions"],
        )

        _add_prediction_header_traces(fig, prediction, row=1, col=1)
        _add_contribution_traces(
            fig, items, labels, values, colors, hover_text, render_options, row=2, col=1
        )

        # Instance values on the right of the body panel (body = row 2 → yaxis2)
        for y_label, val_text in zip(labels, instance_values, strict=False):
            fig.add_annotation(
                x=1.01,
                y=y_label,
                text=val_text,
                xref="paper",
                yref="y2",
                showarrow=False,
                xanchor="left",
                font={"size": 10, "color": "#64748b"},
                align="left",
            )

        # Base prediction uncertainty band in contribution space
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
                        fillcolor="rgba(0,0,0,0.08)",
                        layer="below", line_width=0,
                        row=2, col=1,
                    )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333", row=2, col=1)

        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            margin={"l": 160, "r": 200, "t": 64, "b": 56},
            showlegend=False,
            bargap=0.25,
        )
        if x_range is not None:
            fig.update_xaxes(range=x_range, row=1, col=1)
        if header_x_label:
            fig.update_xaxes(title_text=header_x_label, row=1, col=1)
        fig.update_yaxes(autorange="reversed", row=1, col=1)
        fig.update_xaxes(title_text=x_label_contribution, row=2, col=1)
        fig.update_yaxes(title_text=y_label_contribution, row=2, col=1)
        fig.update_yaxes(autorange="reversed", row=2, col=1)
    else:
        fig = go.Figure()
        _add_contribution_traces(fig, items, labels, values, colors, hover_text, render_options)

        # Instance values on the right of the single-panel body (yaxis = "y")
        for y_label, val_text in zip(labels, instance_values, strict=False):
            fig.add_annotation(
                x=1.01,
                y=y_label,
                text=val_text,
                xref="paper",
                yref="y",
                showarrow=False,
                xanchor="left",
                font={"size": 10, "color": "#64748b"},
                align="left",
            )

        # Base prediction uncertainty band in contribution space
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
                        fillcolor="rgba(0,0,0,0.08)",
                        layer="below", line_width=0,
                    )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333")
        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            xaxis_title=x_label_contribution,
            yaxis_title=y_label_contribution,
            yaxis={"autorange": "reversed"},
            margin={"l": 160, "r": 200, "t": 64, "b": 56},
            showlegend=False,
            bargap=0.25,
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


__all__ = [
    "STYLE_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "ARTIFACT_VERSION",
    "LocalFactualBarsPlotBuilder",
    "LocalFactualBarsPlotRenderer",
    "build_figure",
]
