from __future__ import annotations

import logging
import math
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
    _as_float,
    _collection_for,
    _feature_name,
    _is_alternative_explanation,
    _mode_metadata,
    _normalise_feature_indices,
    _resolve_alternative_rules,
    _select_local_explanation,
    _sequence_get,
    _values_for_features,
)

STYLE_ID = "plotly.local.alternative_bars"
BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
ARTIFACT_VERSION = "0.2.0"

_LOGGER = logging.getLogger(__name__)

# RGB triples for probabilistic / regression coloring
_POS_CLASS_RGB = (37, 99, 235)   # blue  — positive class (predict ≥ pivot)
_NEG_CLASS_RGB = (220, 38, 38)   # red   — negative class (predict < pivot)
_REGRESSION_RGB = (229, 89, 52)  # red-orange — regression
_BASE_INTERVAL_ALPHA = 0.12      # background band opacity
_BAR_ALPHA = 0.55                # interval bar fill opacity


def _warn_fallback(reason: str) -> None:
    message = f"Plotly alternative bars fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _display_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(v) for v in value)
    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(value, np.ndarray):
            return ", ".join(_display_value(v) for v in value.ravel().tolist())
        if isinstance(value, np.generic):
            return str(value.item())
    except ImportError:  # pragma: no cover
        pass
    return str(value)


def _fmt(value: Any, *, signed: bool = False) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "—"
    if signed:
        return f"{numeric:+.4g}"
    return f"{numeric:.4g}"


def _rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha:.2f})"


def _default_options(options: dict[str, Any]) -> dict[str, Any]:
    filter_top = options.get("filter_top")
    hover_detail = str(options.get("hover_detail", "compact"))
    if hover_detail not in {"compact", "full"}:
        raise ValueError("hover_detail must be 'compact' or 'full'.")
    return {
        "filter_top": None if filter_top is None else int(filter_top),
        "show_uncertainty": bool(options.get("show_uncertainty", True)),
        "hover_detail": hover_detail,
    }


def _build_hover(
    rule: str,
    predict: float | None,
    predict_low: float | None,
    predict_high: float | None,
    base_predict: float | None,
    feature_names: list[str],
    feature_values: list[Any],
    *,
    rank: int,
) -> str:
    lines: list[str] = [
        f"<b>Alternative {rank + 1}</b>",
        f"Rule: {rule}",
    ]
    if feature_names:
        lines.append(f"Feature(s): {', '.join(str(n) for n in feature_names)}")
    if feature_values:
        lines.append(
            f"Current value(s): {', '.join(_display_value(v) for v in feature_values)}"
        )
    lines.append("")
    if predict is not None:
        lines.append(f"Alt prediction: {_fmt(predict)}")
    if base_predict is not None and predict is not None:
        lines.append(f"Prediction delta: {_fmt(predict - base_predict, signed=True)}")
    if base_predict is not None:
        lines.append(f"Base prediction: {_fmt(base_predict)}")
    if predict_low is not None and predict_high is not None:
        lines.append(f"Interval: [{_fmt(predict_low)}, {_fmt(predict_high)}]")
        lines.append(f"Interval width: {_fmt(predict_high - predict_low)}")
    return "<br>".join(lines)


def _extract_items(
    local_explanation: Any,
    rules: dict[str, Any],
    *,
    base_predict: float | None,
    base_low: float | None,
    base_high: float | None,
) -> list[dict[str, Any]]:
    collection = _collection_for(local_explanation)
    rule_labels = list(rules.get("rule", ()))
    n = len(rule_labels)
    items: list[dict[str, Any]] = []

    for i in range(n):
        rule = str(_sequence_get(rule_labels, i, f"rule {i}") or f"rule {i}")

        predict: float | None = None
        for key in ("predict", "prediction"):
            v = _sequence_get(rules.get(key, ()), i)
            if v is not None:
                predict = _as_float(v)
                if predict is not None:
                    break

        predict_low: float | None = None
        for key in ("predict_low", "low"):
            v = _sequence_get(rules.get(key, ()), i)
            if v is not None:
                predict_low = _as_float(v)
                if predict_low is not None:
                    break

        predict_high: float | None = None
        for key in ("predict_high", "high"):
            v = _sequence_get(rules.get(key, ()), i)
            if v is not None:
                predict_high = _as_float(v)
                if predict_high is not None:
                    break

        # Skip alternatives identical to the base prediction (matches CE built-in behaviour)
        if (
            predict is not None
            and base_predict is not None
            and predict_low is not None
            and predict_high is not None
            and base_low is not None
            and base_high is not None
            and abs(predict - base_predict) < 1e-10
            and abs(predict_low - base_low) < 1e-10
            and abs(predict_high - base_high) < 1e-10
        ):
            continue

        raw_value = _sequence_get(
            rules.get("feature_value", ()),
            i,
            _sequence_get(rules.get("value", ()), i),
        )
        raw_feature = _sequence_get(rules.get("feature", ()), i)
        feature_indices = _normalise_feature_indices(raw_feature)
        feature_names = [
            _feature_name(collection, fi) or f"Feature {fi}" for fi in feature_indices
        ]
        feature_values = _values_for_features(raw_value, len(feature_indices))

        items.append(
            {
                "original_index": i,
                "rule": rule,
                "predict": predict,
                "predict_low": predict_low,
                "predict_high": predict_high,
                "value": raw_value,
                "feature_names": feature_names,
                "feature_values": feature_values,
            }
        )

    return items


class LocalAlternativeBarsPlotBuilder(PlotBuilder):
    """Build a Plotly artifact for the standard CE alternative explanation bar plot.

    Each row shows the predicted output and calibrated uncertainty interval for one
    independent alternative scenario.  The x-axis is the *predicted output value*,
    not a feature-contribution delta.  A background band marks the base prediction
    interval so users can compare how each alternative shifts the prediction.
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
        is_regression = bool(mode_metadata.get("is_regression", False))

        pred_header = dict(getattr(local_explanation, "prediction", {}) or {})
        base_predict = _as_float(pred_header.get("predict", pred_header.get("prediction")))
        base_low = _as_float(pred_header.get("low", pred_header.get("predict_low")))
        base_high = _as_float(pred_header.get("high", pred_header.get("predict_high")))

        collection = _collection_for(local_explanation)

        # y_minmax for regression x-range
        y_minmax: list[float] | None = None
        y_minmax_raw = getattr(collection, "y_minmax", None)
        if y_minmax_raw is not None:
            try:
                y_minmax = [float(y_minmax_raw[0]), float(y_minmax_raw[1])]
            except (TypeError, IndexError, ValueError):
                y_minmax = None

        # Confidence level for regression axis label
        conf_raw = getattr(collection, "confidence_level", None) or getattr(
            collection, "confidence", None
        )
        confidence_pct = 95
        if conf_raw is not None:
            f_conf = _as_float(conf_raw)
            if f_conf is not None:
                confidence_pct = round(f_conf * 100) if f_conf <= 1.0 else int(f_conf)

        items = _extract_items(
            local_explanation,
            rules,
            base_predict=base_predict,
            base_low=base_low,
            base_high=base_high,
        )

        if options["filter_top"] is not None:
            items = items[: int(options["filter_top"])]

        # Attach hover text now that final display ranks are known
        for rank, item in enumerate(items):
            item["hover"] = _build_hover(
                rule=item["rule"],
                predict=item["predict"],
                predict_low=item["predict_low"],
                predict_high=item["predict_high"],
                base_predict=base_predict,
                feature_names=item["feature_names"],
                feature_values=item["feature_values"],
                rank=rank,
            )

        # Axis metadata
        if is_regression:
            if y_minmax is not None:
                xlim = y_minmax
            else:
                finite_vals = [
                    v
                    for item in items
                    for v in (item["predict_low"], item["predict_high"])
                    if v is not None and math.isfinite(v)
                ]
                for v in (base_low, base_high, base_predict):
                    if v is not None and math.isfinite(v):
                        finite_vals.append(v)
                if finite_vals:
                    span = max(finite_vals) - min(finite_vals)
                    margin = span * 0.05 or 0.1
                    xlim = [min(finite_vals) - margin, max(finite_vals) + margin]
                else:
                    xlim = [0.0, 1.0]
            pivot = None
            x_label = f"Prediction interval with {confidence_pct}% confidence"
            xticks = None
        else:
            xlim = [0.0, 1.0]
            pivot = 0.5
            x_label = "Probability"
            xticks = [round(i * 0.1, 1) for i in range(11)]

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "base_prediction": {
                "predict": base_predict,
                "low": base_low,
                "high": base_high,
            },
            "items": items,
            "axis_metadata": {
                "xlim": xlim,
                "xticks": xticks,
                "pivot": pivot,
                "x_label": x_label,
                "y_label": "Alternative rules",
            },
            "options_used": {
                "filter_top": options["filter_top"],
                "show_uncertainty": options["show_uncertainty"],
                "hover_detail": options["hover_detail"],
            },
            "metadata": {
                "num_alternatives": len(items),
                "is_regression": is_regression,
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


# ── Renderer helpers ────────────────────────────────────────────────────────


def _bar_color(predict: float | None, pivot: float | None) -> str:
    """Interval bar fill color: intensity scales with distance from the pivot."""
    if predict is None:
        return _rgba((100, 116, 139), _BAR_ALPHA)
    if pivot is None:
        return _rgba(_REGRESSION_RGB, _BAR_ALPHA)
    dist = abs(predict - pivot)
    intensity = min(1.0, 0.35 + 0.65 * (dist / 0.5))
    rgb = _POS_CLASS_RGB if predict >= pivot else _NEG_CLASS_RGB
    return _rgba(rgb, intensity * _BAR_ALPHA)


def _marker_color(predict: float | None, pivot: float | None) -> str:
    """Solid colour for the prediction-point marker."""
    if predict is None:
        return _rgba((100, 116, 139), 1.0)
    if pivot is None:
        return _rgba(_REGRESSION_RGB, 1.0)
    dist = abs(predict - pivot)
    intensity = min(1.0, 0.5 + 0.5 * (dist / 0.5))
    rgb = _POS_CLASS_RGB if predict >= pivot else _NEG_CLASS_RGB
    return _rgba(rgb, intensity)


def _title_for(artifact: PlotArtifact, options: dict[str, Any]) -> str:
    n_alts = int((artifact.get("metadata") or {}).get("num_alternatives", 0))
    task = artifact.get("task") or ""
    base_pred = dict(artifact.get("base_prediction", {}) or {})
    base = _as_float(base_pred.get("predict"))
    parts = [f"Alternative explanations ({n_alts} independent scenarios)"]
    if task:
        parts[0] += f" — {task}"
    if base is not None:
        parts.append(f"Base prediction: {_fmt(base)}")
    return " | ".join(parts)


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    """Render a CE alternative bars artifact as a Plotly horizontal interval chart.

    Each row shows the calibrated prediction interval under that alternative scenario.
    A background band marks the base prediction interval for visual comparison.
    Bars are NOT additive — each row is an independent scenario.
    Hover cards show rule text, feature context, and prediction details.
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    render_options = dict(artifact.get("options_used", {}) or {})
    render_options.update(options)

    items = list(artifact.get("items", ()))
    base_pred = dict(artifact.get("base_prediction", {}) or {})
    axis_meta = dict(artifact.get("axis_metadata", {}) or {})

    base_predict = _as_float(base_pred.get("predict"))
    base_low = _as_float(base_pred.get("low"))
    base_high = _as_float(base_pred.get("high"))

    xlim: list[float] = list(axis_meta.get("xlim") or [0.0, 1.0])
    xticks = axis_meta.get("xticks")
    pivot = axis_meta.get("pivot")  # 0.5 for classification, None for regression
    x_label = axis_meta.get("x_label", "Value")
    is_regression = pivot is None

    if not items:
        fig = go.Figure()
        fig.update_layout(template="plotly_white", title="No alternatives available")
        return fig

    y_labels = [str(item.get("rule", "")) for item in items]
    x_lo, x_hi = float(xlim[0]), float(xlim[1])

    # Pre-compute per-item plotting values
    bar_bases: list[float] = []
    bar_widths: list[float] = []
    predict_xs: list[float | None] = []
    bar_colors: list[str] = []
    marker_colors_list: list[str] = []
    hover_texts: list[str] = []

    for item in items:
        pred = _as_float(item.get("predict"))
        lo = _as_float(item.get("predict_low"))
        hi = _as_float(item.get("predict_high"))

        # Replace infinities, then clamp to x-range
        if lo is not None:
            lo = x_lo if not math.isfinite(lo) else max(x_lo, min(x_hi, lo))
        if hi is not None:
            hi = x_hi if not math.isfinite(hi) else max(x_lo, min(x_hi, hi))

        base_val = lo if lo is not None else (pred if pred is not None else x_lo)
        width = (hi - lo) if (lo is not None and hi is not None) else 0.0

        bar_bases.append(base_val)
        bar_widths.append(width)
        predict_xs.append(pred)
        bar_colors.append(_bar_color(pred, pivot))
        marker_colors_list.append(_marker_color(pred, pivot))
        hover_texts.append(str(item.get("hover", "")))

    fig = go.Figure()

    # ── 1. Base prediction interval background band ──────────────────────────
    if base_low is not None and base_high is not None:
        eff_lo = x_lo if not math.isfinite(base_low) else max(x_lo, base_low)
        eff_hi = x_hi if not math.isfinite(base_high) else min(x_hi, base_high)
        if eff_lo < eff_hi:
            if pivot is not None and eff_lo < pivot < eff_hi:
                # Split at the decision boundary
                fig.add_vrect(
                    x0=eff_lo,
                    x1=pivot,
                    fillcolor=_rgba(_NEG_CLASS_RGB, _BASE_INTERVAL_ALPHA),
                    layer="below",
                    line_width=0,
                )
                fig.add_vrect(
                    x0=pivot,
                    x1=eff_hi,
                    fillcolor=_rgba(_POS_CLASS_RGB, _BASE_INTERVAL_ALPHA),
                    layer="below",
                    line_width=0,
                )
            else:
                if is_regression:
                    rgb: tuple[int, int, int] = (100, 116, 139)
                elif base_predict is not None and base_predict >= (pivot or 0.5):
                    rgb = _POS_CLASS_RGB
                else:
                    rgb = _NEG_CLASS_RGB
                fig.add_vrect(
                    x0=eff_lo,
                    x1=eff_hi,
                    fillcolor=_rgba(rgb, _BASE_INTERVAL_ALPHA),
                    layer="below",
                    line_width=0,
                )

    # ── 2. Regression: dashed vertical line at base prediction ──────────────
    if is_regression and base_predict is not None:
        fig.add_vline(
            x=base_predict,
            line_width=1.5,
            line_color="rgba(100,116,139,0.5)",
            line_dash="dash",
        )

    # ── 3. Classification: dotted pivot line at 0.5 ─────────────────────────
    if pivot is not None:
        fig.add_vline(
            x=pivot,
            line_width=1,
            line_color="rgba(100,116,139,0.3)",
            line_dash="dot",
        )

    # ── 4. Interval bars: go.Bar with base=predict_low ──────────────────────
    # Each bar spans [predict_low, predict_high] for one alternative scenario.
    fig.add_trace(
        go.Bar(
            x=bar_widths,
            y=y_labels,
            base=bar_bases,
            orientation="h",
            marker={"color": bar_colors, "line": {"width": 0}},
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
            name="interval",
        )
    )

    # ── 5. Prediction markers: vertical tick at the predicted value ──────────
    fig.add_trace(
        go.Scatter(
            x=predict_xs,
            y=y_labels,
            mode="markers",
            marker={
                "symbol": "line-ns-open",
                "size": 14,
                "color": marker_colors_list,
                "line": {"width": 2.5, "color": marker_colors_list},
            },
            hoverinfo="skip",
            showlegend=False,
            name="prediction",
        )
    )

    # ── 6. Right-side annotations: current feature / instance values ─────────
    for y_label, item in zip(y_labels, items, strict=False):
        fig.add_annotation(
            x=1.01,
            y=y_label,
            text=_display_value(item.get("value")),
            xref="paper",
            yref="y",
            showarrow=False,
            xanchor="left",
            font={"size": 10, "color": "#64748b"},
            align="left",
        )

    # ── 7. Layout ────────────────────────────────────────────────────────────
    xaxis_cfg: dict[str, Any] = {
        "title": x_label,
        "range": [x_lo, x_hi],
    }
    if xticks is not None:
        xaxis_cfg["tickvals"] = xticks

    fig.update_layout(
        template="plotly_white",
        title=_title_for(artifact, render_options),
        xaxis=xaxis_cfg,
        yaxis={
            "title": axis_meta.get("y_label", "Alternative rules"),
            "autorange": "reversed",
        },
        margin={"l": 240, "r": 200, "t": 64, "b": 56},
        showlegend=False,
        bargap=0.4,
    )

    return fig


class LocalAlternativeBarsPlotRenderer(PlotRenderer):
    """Render alternative bar artifacts as Plotly horizontal interval charts.

    Each row is an independent alternative scenario — bars are NOT stacked
    additive contributions.
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
