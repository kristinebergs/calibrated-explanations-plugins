from __future__ import annotations

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

from .alternative_feature_summary import (
    _as_bool,
    _as_float,
    _collection_for,
    _conjunction_size,
    _feature_name,
    _is_alternative_explanation,
    _mode_metadata,
    _normalise_feature_indices,
    _resolve_alternative_rules,
    _resolve_ce_memberships,
    _resolve_primary_role,
    _resolve_quality_flag,
    _role_quality_key,
    _select_local_explanation,
    _sequence_get,
    _serialise_value,
    _values_for_features,
)

STYLE_ID = "plotly.local.alternative_bars"
BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
ARTIFACT_VERSION = "0.1.0"

_LOGGER = logging.getLogger(__name__)

_ROLE_COLORS = {
    "counter": "#2563eb",
    "super": "#16a34a",
    "semi": "#d97706",
    "unknown": "#64748b",
}
_COMPONENT_OPACITY = 0.6
_INTERVAL_COLOR = "rgba(45, 55, 72, 0.45)"
_ROLE_SORT_ORDER = {"counter": 0, "super": 1, "semi": 2, "unknown": 3}


def _warn_fallback(reason: str) -> None:
    message = f"Plotly alternative bars fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _display_value(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in value)
    try:
        import numpy as np  # noqa: PLC0415

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


def _rule_predict(rules: dict[str, Any], rule_index: int) -> float | None:
    for key in ("predict", "prediction"):
        values = rules.get(key)
        if values is not None:
            v = _sequence_get(values, rule_index)
            if v is not None:
                return _as_float(v)
    return None


def _rule_predict_low(rules: dict[str, Any], rule_index: int) -> float | None:
    for key in ("predict_low", "low"):
        values = rules.get(key)
        if values is not None:
            v = _sequence_get(values, rule_index)
            if v is not None:
                return _as_float(v)
    return None


def _rule_predict_high(rules: dict[str, Any], rule_index: int) -> float | None:
    for key in ("predict_high", "high"):
        values = rules.get(key)
        if values is not None:
            v = _sequence_get(values, rule_index)
            if v is not None:
                return _as_float(v)
    return None


def _default_options(options: dict[str, Any]) -> dict[str, Any]:
    filter_top = options.get("filter_top")
    sort_by = str(options.get("sort_by", "original"))
    if sort_by not in {"original", "prediction_delta", "interval_width", "role", "feature"}:
        raise ValueError(
            "sort_by must be one of original, prediction_delta, interval_width, role, or feature."
        )
    unknown_policy = str(options.get("unknown_policy", "show"))
    if unknown_policy not in {"show", "hide"}:
        raise ValueError("unknown_policy must be 'show' or 'hide'.")
    hover_detail = str(options.get("hover_detail", "compact"))
    if hover_detail not in {"compact", "full"}:
        raise ValueError("hover_detail must be 'compact' or 'full'.")
    return {
        "filter_top": None if filter_top is None else int(filter_top),
        "sort_by": sort_by,
        "show_uncertainty": bool(options.get("show_uncertainty", True)),
        "hover_uncertainty": bool(options.get("hover_uncertainty", True)),
        "show_prediction_header": bool(options.get("show_prediction_header", True)),
        "hover_detail": hover_detail,
        "include_conjunctive_components": bool(options.get("include_conjunctive_components", True)),
        "unknown_policy": unknown_policy,
    }


def _build_hover(
    record: dict[str, Any],
    *,
    base_prediction: float | None,
    options: dict[str, Any],
    component_name: str | None = None,
    component_value: Any = None,
) -> str:
    alt_rank = record.get("alt_rank", record.get("original_index", 0))
    lines = [
        f"Alternative: {alt_rank + 1 if isinstance(alt_rank, int) else alt_rank}",
        f"Rule: {_display_value(record.get('rule'))}",
    ]
    if component_name is not None:
        lines.append(f"Component feature: {_display_value(component_name)}")
        lines.append(f"Component value: {_display_value(component_value)}")
    else:
        feature_names = record.get("feature_names")
        if feature_names:
            lines.append(f"Feature(s): {_display_value(feature_names)}")
        feature_values = record.get("feature_values")
        if feature_values:
            lines.append(f"Current value(s): {_display_value(feature_values)}")

    prediction = record.get("prediction")
    predict_low = record.get("predict_low")
    predict_high = record.get("predict_high")

    if prediction is not None:
        lines.append(f"Alt prediction: {_format_number(prediction)}")
    if base_prediction is not None and prediction is not None:
        delta = float(prediction) - base_prediction
        lines.append(f"Prediction delta: {_format_number(delta, signed=True)}")
    if base_prediction is not None:
        lines.append(f"Base prediction: {_format_number(base_prediction)}")

    if options.get("hover_uncertainty", True):
        if predict_low is not None and predict_high is not None:
            lo = _format_number(predict_low)
            hi = _format_number(predict_high)
            lines.append(f"Prediction interval: [{lo}, {hi}]")
            interval_width = record.get("interval_width")
            if interval_width is not None:
                lines.append(f"Interval width: {_format_number(interval_width)}")
        else:
            lines.append("Interval: unavailable")

    role = record.get("primary_role", "unknown")
    role_source = record.get("role_source", "unavailable")
    if role_source == "unavailable":
        lines.append("Role: unknown (role information unavailable)")
    elif role_source == "heuristic":
        lines.append(f"Role: {role} (inferred)")
    else:
        lines.append(f"Role: {role} (explicit)")

    if options.get("hover_detail") == "full":
        is_ensured = record.get("is_ensured", False)
        is_pareto = record.get("is_pareto", False)
        lines.append(f"Ensured: {'yes' if is_ensured else 'no'}")
        lines.append(f"Pareto: {'yes' if is_pareto else 'no'}")
        if record.get("is_conjunction"):
            lines.append(f"Conjunction size: {record.get('rule_size', 1)}")
            lines.append("Note: component values share total prediction delta equally")

    return "<br>".join(lines)


def _extract_records(
    local_explanation: Any,
    rules: dict[str, Any],
    *,
    base_prediction: float | None,
    mode_metadata: dict[str, Any],
    options: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    collection = _collection_for(local_explanation)
    ce_memberships = _resolve_ce_memberships(local_explanation, rules)
    rule_labels = list(rules.get("rule", ()))
    num_rules = len(rule_labels)
    records: list[dict[str, Any]] = []
    num_missing_intervals = 0

    for rule_index in range(num_rules):
        raw_rule = _sequence_get(rule_labels, rule_index, f"rule {rule_index}")
        rule_condition = str(raw_rule).strip() if raw_rule is not None else f"rule {rule_index}"
        raw_feature = _sequence_get(rules.get("feature", ()), rule_index)
        feature_indices = _normalise_feature_indices(raw_feature)
        feature_names = [
            _feature_name(collection, fi) or f"Feature {fi}" for fi in feature_indices
        ]
        raw_true_value = _sequence_get(
            rules.get("feature_value", ()),
            rule_index,
            _sequence_get(rules.get("value", ()), rule_index),
        )
        feature_values = _values_for_features(raw_true_value, len(feature_indices))
        is_conjunctive = bool(
            _as_bool(_sequence_get(rules.get("is_conjunctive", ()), rule_index)) or False
        )
        rule_size = _conjunction_size(feature_indices, rule_condition, is_conjunctive)
        is_conjunction = rule_size > 1

        prediction = _rule_predict(rules, rule_index)
        predict_low = _rule_predict_low(rules, rule_index)
        predict_high = _rule_predict_high(rules, rule_index)

        if predict_low is None or predict_high is None:
            num_missing_intervals += 1
            interval_width = None
        else:
            interval_width = predict_high - predict_low

        primary_role, role_source, role_metadata = _resolve_primary_role(
            rules=rules,
            rule_index=rule_index,
            rule_condition=rule_condition,
            prediction=prediction,
            base_prediction=base_prediction,
            mode_metadata=mode_metadata,
            options=options,
            ce_memberships=ce_memberships,
        )
        is_ensured = _resolve_quality_flag(
            rules,
            rule_index,
            ("is_ensured", "ensured", "ensured_rule", "is_ensured_rule"),
        ) or rule_index in ce_memberships.get("ensured", set())
        is_pareto = _resolve_quality_flag(
            rules,
            rule_index,
            ("is_pareto", "pareto", "pareto_optimal", "is_pareto_optimal"),
        ) or rule_index in ce_memberships.get("pareto", set())
        quality_flags = [
            flag for flag, active in (("ensured", is_ensured), ("pareto", is_pareto)) if active
        ]

        if prediction is not None and base_prediction is not None:
            bar_value = prediction - base_prediction
            bar_value_kind = "prediction_delta"
        elif prediction is not None:
            bar_value = prediction
            bar_value_kind = "prediction"
        else:
            bar_value = None
            bar_value_kind = "unavailable"

        record = {
            "original_index": rule_index,
            "alt_rank": rule_index,
            "rule": rule_condition,
            "feature_indices": [_serialise_value(fi) for fi in feature_indices],
            "feature_names": feature_names,
            "feature_values": feature_values,
            "is_conjunction": is_conjunction,
            "rule_size": rule_size,
            "prediction": prediction,
            "predict_low": predict_low,
            "predict_high": predict_high,
            "interval_width": interval_width,
            "primary_role": primary_role,
            "role_source": role_source,
            "is_ensured": is_ensured,
            "is_pareto": is_pareto,
            "quality_flags": quality_flags,
            "role_quality_key": _role_quality_key(primary_role, quality_flags),
            "bar_value": bar_value,
            "bar_value_kind": bar_value_kind,
            "metadata": role_metadata,
        }
        records.append(record)

    return records, num_missing_intervals


def _sort_records(
    records: list[dict[str, Any]],
    sort_by: str,
    base_prediction: float | None,
) -> list[dict[str, Any]]:
    if sort_by == "original":
        return list(records)
    if sort_by == "prediction_delta":

        def delta_key(r: dict[str, Any]) -> float:
            p = _as_float(r.get("prediction"))
            if p is None:
                return 0.0
            if base_prediction is not None:
                return -abs(p - base_prediction)
            return -abs(p)

        return sorted(records, key=lambda r: (delta_key(r), r["original_index"]))
    if sort_by == "interval_width":
        return sorted(
            records,
            key=lambda r: (
                -(r["interval_width"] if r["interval_width"] is not None else -1.0),
                r["original_index"],
            ),
        )
    if sort_by == "role":
        return sorted(
            records,
            key=lambda r: (
                _ROLE_SORT_ORDER.get(r.get("primary_role", "unknown"), 3),
                r["original_index"],
            ),
        )
    # feature
    return sorted(
        records,
        key=lambda r: (
            str(r.get("feature_names") or ""),
            r["original_index"],
        ),
    )


def _build_items(
    records: list[dict[str, Any]],
    *,
    base_prediction: float | None,
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    include_components = bool(options.get("include_conjunctive_components", True))
    items: list[dict[str, Any]] = []

    for display_rank, record in enumerate(records):
        rule_text = record["rule"]
        is_conjunction = record["is_conjunction"]
        rule_size = record["rule_size"]
        bar_value = record["bar_value"]
        primary_role = record["primary_role"]

        # Build y_label for the main alternative bar
        label_prefix = f"[{display_rank + 1}]"
        if is_conjunction:
            y_label = f"{label_prefix} {rule_text} (conj.)"
        else:
            y_label = f"{label_prefix} {rule_text}"

        hover = _build_hover(record, base_prediction=base_prediction, options=options)

        main_item = {
            "id": f"alt-{record['original_index']}",
            "original_index": record["original_index"],
            "alt_rank": display_rank,
            "y_label": y_label,
            "bar_value": bar_value,
            "bar_value_kind": record["bar_value_kind"],
            "primary_role": primary_role,
            "role_quality_key": record["role_quality_key"],
            "is_ensured": record["is_ensured"],
            "is_pareto": record["is_pareto"],
            "is_component": False,
            "is_conjunction": is_conjunction,
            "rule_size": rule_size,
            "rule": rule_text,
            "feature_names": record["feature_names"],
            "feature_values": record["feature_values"],
            "prediction": record["prediction"],
            "predict_low": record["predict_low"],
            "predict_high": record["predict_high"],
            "interval_width": record["interval_width"],
            "hover": hover,
            "metadata": record.get("metadata", {}),
        }
        items.append(main_item)

        if is_conjunction and include_components:
            # Each conjunctive component shares the total prediction delta equally
            n = max(1, rule_size)
            component_bar_value = (bar_value / n) if bar_value is not None else None
            for comp_idx, (feat_name, feat_val) in enumerate(
                zip(record["feature_names"], record["feature_values"], strict=False)
            ):
                comp_hover = _build_hover(
                    record,
                    base_prediction=base_prediction,
                    options=options,
                    component_name=feat_name,
                    component_value=feat_val,
                )
                comp_item = {
                    "id": f"alt-{record['original_index']}-comp-{comp_idx}",
                    "original_index": record["original_index"],
                    "alt_rank": display_rank,
                    "y_label": f"  └ {feat_name}",
                    "bar_value": component_bar_value,
                    "bar_value_kind": record["bar_value_kind"],
                    "primary_role": primary_role,
                    "role_quality_key": record["role_quality_key"],
                    "is_ensured": record["is_ensured"],
                    "is_pareto": record["is_pareto"],
                    "is_component": True,
                    "is_conjunction": True,
                    "rule_size": rule_size,
                    "rule": rule_text,
                    "feature_names": [feat_name],
                    "feature_values": [feat_val],
                    "prediction": record["prediction"],
                    "predict_low": record["predict_low"],
                    "predict_high": record["predict_high"],
                    "interval_width": record["interval_width"],
                    "hover": comp_hover,
                    "metadata": record.get("metadata", {}),
                }
                items.append(comp_item)

    return items


class LocalAlternativeBarsPlotBuilder(PlotBuilder):
    """Build a Plotly artifact for local alternative explanation bars.

    Each alternative rule is rendered as an independent visual bar. Alternatives
    are not stacked or summed — they are independent candidate explanations.
    """

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
        if intent_type not in (None, "alternative"):
            raise ValueError(f"{STYLE_ID} supports alternative local explanations only.")

        options = _default_options(dict(context.options))
        local_explanation = _select_local_explanation(
            context.explanation, context.options.get("instance_index")
        )
        if not _is_alternative_explanation(local_explanation):
            raise ValueError(
                f"{STYLE_ID} requires an alternative explanation. "
                "Use plotly.local.factual_bars for factual explanations."
            )

        rules = _resolve_alternative_rules(local_explanation)
        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        prediction_header = dict(getattr(local_explanation, "prediction", {}) or {})
        base_prediction = _as_float(
            prediction_header.get("predict", prediction_header.get("prediction"))
        )

        records, num_missing_intervals = _extract_records(
            local_explanation,
            rules,
            base_prediction=base_prediction,
            mode_metadata=mode_metadata,
            options=options,
        )

        unknown_policy = options["unknown_policy"]
        if unknown_policy == "hide":
            records = [r for r in records if r["primary_role"] != "unknown"]

        sorted_records = _sort_records(records, options["sort_by"], base_prediction)
        if options["filter_top"] is not None:
            sorted_records = sorted_records[: int(options["filter_top"])]

        items = _build_items(sorted_records, base_prediction=base_prediction, options=options)

        all_kinds = {item["bar_value_kind"] for item in items}
        bar_value_kind = (
            "prediction_delta"
            if "prediction_delta" in all_kinds
            else "prediction"
            if "prediction" in all_kinds
            else "unavailable"
        )

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "base_prediction": base_prediction,
            "base_prediction_header": prediction_header,
            "items": items,
            "axis_metadata": {
                "x_label": (
                    "Prediction delta (alt − base)"
                    if bar_value_kind == "prediction_delta"
                    else "Prediction value"
                    if bar_value_kind == "prediction"
                    else "Value"
                ),
                "y_label": "Alternative rule / feature",
                "zero_line": bar_value_kind == "prediction_delta",
            },
            "options_used": {
                "filter_top": options["filter_top"],
                "sort_by": options["sort_by"],
                "show_uncertainty": options["show_uncertainty"],
                "hover_uncertainty": options["hover_uncertainty"],
                "show_prediction_header": options["show_prediction_header"],
                "hover_detail": options["hover_detail"],
                "include_conjunctive_components": options["include_conjunctive_components"],
                "unknown_policy": unknown_policy,
            },
            "metadata": {
                "num_alternatives": len(sorted_records),
                "num_items": len(items),
                "num_missing_intervals": num_missing_intervals,
                "bar_value_kind": bar_value_kind,
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


def _role_color(primary_role: str, is_component: bool = False) -> str:
    base = _ROLE_COLORS.get(primary_role, _ROLE_COLORS["unknown"])
    if is_component:
        # Lighten component bars by hex-blending toward white (approx)
        try:
            r = int(base[1:3], 16)
            g = int(base[3:5], 16)
            b = int(base[5:7], 16)
            r = int(r + (255 - r) * 0.45)
            g = int(g + (255 - g) * 0.45)
            b = int(b + (255 - b) * 0.45)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return base
    return base


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    """Render alternative bars artifact as a Plotly horizontal bar chart."""
    import plotly.graph_objects as go

    render_options = dict(artifact.get("options_used", {}) or {})
    render_options.update(options)

    items = list(artifact.get("items", ()))
    if not items:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            title="No alternatives available",
        )
        return fig

    y_labels = [str(item.get("y_label") or item.get("id")) for item in items]
    bar_values = [
        float(item["bar_value"]) if item.get("bar_value") is not None else 0.0 for item in items
    ]
    colors = [
        _role_color(item.get("primary_role", "unknown"), item.get("is_component", False))
        for item in items
    ]
    hover_text = [str(item.get("hover") or "") for item in items]

    axis_meta = dict(artifact.get("axis_metadata", {}) or {})
    show_prediction_header = bool(render_options.get("show_prediction_header", True))
    base_prediction = artifact.get("base_prediction")
    base_prediction_header = dict(artifact.get("base_prediction_header", {}) or {})

    # Determine if we need the prediction-header row
    use_header = (
        show_prediction_header
        and base_prediction is not None
    )

    if use_header:
        from plotly.subplots import make_subplots  # noqa: PLC0415

        fig = make_subplots(
            rows=2,
            cols=1,
            row_heights=[0.18, 0.82],
            shared_xaxes=False,
            vertical_spacing=0.06,
            subplot_titles=["Base prediction", "Alternative explanations (independent)"],
        )

        # Header: base prediction bar
        p_val = base_prediction
        p_low = _as_float(
            base_prediction_header.get("low", base_prediction_header.get("predict_low"))
        )
        p_high = _as_float(
            base_prediction_header.get("high", base_prediction_header.get("predict_high"))
        )
        header_hover_lines = [f"Base prediction: {_format_number(p_val)}"]
        if p_low is not None and p_high is not None:
            header_hover_lines.append(
                f"Interval: [{_format_number(p_low)}, {_format_number(p_high)}]"
            )
        header_hover = "<br>".join(header_hover_lines)

        fig.add_trace(
            go.Bar(
                x=[p_val],
                y=["base"],
                orientation="h",
                marker={"color": "#64748b"},
                hovertext=[header_hover],
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
                name="base prediction",
            ),
            row=1,
            col=1,
        )
        if p_low is not None and p_high is not None:
            fig.add_trace(
                go.Scatter(
                    x=[float(p_low), float(p_high)],
                    y=["base", "base"],
                    mode="lines",
                    line={"color": _INTERVAL_COLOR, "width": 6},
                    hoverinfo="skip",
                    showlegend=False,
                    name="base interval",
                ),
                row=1,
                col=1,
            )

        # Main bars in row 2
        fig.add_trace(
            go.Bar(
                x=bar_values,
                y=y_labels,
                orientation="h",
                marker={"color": colors},
                hovertext=hover_text,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
                name="alternative",
            ),
            row=2,
            col=1,
        )

        if bool(render_options.get("show_uncertainty", True)):
            x_unc: list[float | None] = []
            y_unc: list[str | None] = []
            for label, item in zip(y_labels, items, strict=False):
                p_lo = item.get("predict_low")
                p_hi = item.get("predict_high")
                bv = item.get("bar_value")
                base = artifact.get("base_prediction")
                if p_lo is None or p_hi is None:
                    continue
                if bv is not None and item.get("bar_value_kind") == "prediction_delta":
                    eff_low = float(p_lo) - (base if base else 0.0)
                    eff_high = float(p_hi) - (base if base else 0.0)
                else:
                    eff_low = float(p_lo)
                    eff_high = float(p_hi)
                x_unc.extend([eff_low, eff_high, None])
                y_unc.extend([label, label, None])
            if x_unc:
                fig.add_trace(
                    go.Scatter(
                        x=x_unc,
                        y=y_unc,
                        mode="lines",
                        line={"color": _INTERVAL_COLOR, "width": 5},
                        hoverinfo="skip",
                        showlegend=False,
                        name="prediction interval",
                    ),
                    row=2,
                    col=1,
                )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333", row=2, col=1)

        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            margin={"l": 220, "r": 28, "t": 64, "b": 56},
            showlegend=False,
            bargap=0.2,
        )
        fig.update_xaxes(title_text=axis_meta.get("x_label", "Value"), row=2, col=1)
        fig.update_yaxes(autorange="reversed", row=2, col=1)

    else:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=bar_values,
                y=y_labels,
                orientation="h",
                marker={"color": colors},
                hovertext=hover_text,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
                name="alternative",
            )
        )

        if bool(render_options.get("show_uncertainty", True)):
            x_unc = []
            y_unc = []
            for label, item in zip(y_labels, items, strict=False):
                p_lo = item.get("predict_low")
                p_hi = item.get("predict_high")
                base = artifact.get("base_prediction")
                if p_lo is None or p_hi is None:
                    continue
                if item.get("bar_value_kind") == "prediction_delta":
                    eff_low = float(p_lo) - (base if base else 0.0)
                    eff_high = float(p_hi) - (base if base else 0.0)
                else:
                    eff_low = float(p_lo)
                    eff_high = float(p_hi)
                x_unc.extend([eff_low, eff_high, None])
                y_unc.extend([label, label, None])
            if x_unc:
                fig.add_trace(
                    go.Scatter(
                        x=x_unc,
                        y=y_unc,
                        mode="lines",
                        line={"color": _INTERVAL_COLOR, "width": 5},
                        hoverinfo="skip",
                        showlegend=False,
                        name="prediction interval",
                    )
                )

        if axis_meta.get("zero_line", True):
            fig.add_vline(x=0, line_width=1, line_color="#333333")

        fig.update_layout(
            template="plotly_white",
            title=_title_for(artifact, render_options),
            xaxis_title=axis_meta.get("x_label", "Value"),
            yaxis_title=axis_meta.get("y_label", "Alternative rule / feature"),
            yaxis={"autorange": "reversed"},
            margin={"l": 220, "r": 28, "t": 64, "b": 56},
            showlegend=False,
            bargap=0.2,
        )

    return fig


def _title_for(artifact: PlotArtifact, options: dict[str, Any]) -> str:
    n_alts = int((artifact.get("metadata") or {}).get("num_alternatives", 0))
    task = artifact.get("task") or ""
    base = artifact.get("base_prediction")
    parts = [f"Local alternative explanations ({n_alts} independent alternatives)"]
    if task:
        parts[0] += f" — {task}"
    if bool(options.get("show_prediction_header", True)) and base is not None:
        parts.append(f"Base prediction: {_format_number(base)}")
    return " | ".join(parts)


class LocalAlternativeBarsPlotRenderer(PlotRenderer):
    """Render alternative bar artifacts as Plotly horizontal bar charts.

    Each alternative rule is a visually independent bar, not a stacked contribution.
    """

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
                f"Plotly is required to render {STYLE_ID}. "
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
    "LocalAlternativeBarsPlotBuilder",
    "LocalAlternativeBarsPlotRenderer",
    "build_figure",
]
