from __future__ import annotations

import contextlib
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

from ._version import PACKAGE_VERSION, PROVIDER
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

# Legacy CE fill-color function, replicated inline for exact visual parity with
# CE's legacy/PlotSpec rendering. The upstream implementation
# (calibrated_explanations.viz.builders._legacy_get_fill_color) is a private CE
# member, so it is NOT imported at runtime; instead this copy is the canonical
# implementation and tests/parity compare it against the CE original when that
# private symbol is available (see test_alternative_bars.py).
def _ce_brew2() -> list[tuple[int, int, int]]:
    import numpy as np  # noqa: PLC0415

    color_list: list[tuple[int, int, int]] = []
    s, v = 0.75, 0.9
    c, m = s * v, v - s * v
    for h in np.arange(5, 385, 245).astype(int):
        h_bar = h / 60.0
        x = c * (1 - abs((h_bar % 2) - 1))
        rgb_lut = [
            (c, x, 0), (x, c, 0), (0, c, x), (0, x, c),
            (x, 0, c), (c, 0, x), (c, x, 0),
        ]
        r, g, b = rgb_lut[int(h_bar)]
        color_list.append((int(255 * (r + m)), int(255 * (g + m)), int(255 * (b + m))))
    color_list.reverse()
    return color_list


def _ce_fill_color(probability: float, reduction: float = 1.0) -> str:
    colors = _ce_brew2()
    winner = int(probability >= 0.5)
    color = colors[winner]
    alpha = probability if winner == 1 else 1.0 - probability
    alpha = ((alpha - 0.5) / 0.5) * 0.75 + 0.25
    if reduction != 1.0:
        alpha = reduction
    blended = [int(round(alpha * c + (1 - alpha) * 255)) for c in color]
    close = math.isfinite(probability) and math.isclose(
        probability, 1.0, rel_tol=1e-9, abs_tol=1e-12
    )
    if reduction == 1.0 and close:
        return "#ff0000"
    return "#{:02x}{:02x}{:02x}".format(*blended)


_REGRESSION_BAR_COLOR: str = _ce_fill_color(1.0, 1.0)   # "#ff0000"
_REGRESSION_BASE_COLOR: str = _ce_fill_color(1.0, 0.15)


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


def _default_options(options: dict[str, Any]) -> dict[str, Any]:
    filter_top = options.get("filter_top")
    hover_detail = str(options.get("hover_detail", "compact"))
    if hover_detail not in {"compact", "full"}:
        raise ValueError("hover_detail must be 'compact' or 'full'.")
    # CE's collection-level plot forwards rnk_metric/rnk_weight as None when the
    # caller did not set them; None means "use this style's default".
    rnk_metric = str(options.get("rnk_metric") or "ensured")
    if rnk_metric not in {"ensured", "feature_weight", "uncertainty"}:
        raise ValueError("rnk_metric must be 'ensured', 'feature_weight', or 'uncertainty'.")
    rnk_weight_raw = options.get("rnk_weight")
    rnk_weight = 0.5 if rnk_weight_raw is None else float(rnk_weight_raw)
    if not 0.0 <= rnk_weight <= 1.0:
        raise ValueError("rnk_weight must be in [0.0, 1.0].")
    if "show_uncertainty" in options:
        # Parity ledger BARS-025: CE core has no such toggle for alternative
        # plots — calibrated intervals are always drawn. Accepting the option
        # silently would suggest it does something.
        message = (
            "show_uncertainty has no effect for plotly.local.alternative_bars: "
            "calibrated prediction intervals are always shown, matching CE core."
        )
        _LOGGER.info(message)
        warnings.warn(message, UserWarning, stacklevel=4)
    # CE core maps "uncertainty" to "ensured" with rnk_weight=1.0
    if rnk_metric == "uncertainty":
        rnk_metric = "ensured"
        rnk_weight = 1.0
    return {
        "filter_top": None if filter_top is None else int(filter_top),
        "show_uncertainty": bool(options.get("show_uncertainty", True)),
        "hover_detail": hover_detail,
        "rnk_metric": rnk_metric,
        "rnk_weight": rnk_weight,
    }


def _rank_items(
    items: list[dict[str, Any]],
    *,
    rnk_metric: str,
    rnk_weight: float,
    base_predict: float | None,
    is_classification: bool,
    local_explanation: Any = None,
) -> list[dict[str, Any]]:
    """Rank items through CE's public ranking APIs (parity ledger BARS-004).

    Mirrors ``AlternativeExplanation.plot`` on CE 1.0.x exactly:

    * ``feature_weight``: ``rank_features(weights, width=weight_high-weight_low)``
      — |weight| primary key, weight-interval width as tie-break.
    * ``ensured`` (the ``uncertainty`` alias is mapped to ``ensured`` with
      ``rnk_weight=1.0`` in ``_default_options``, as in CE core):
      ``calculate_metrics`` score ``(1-w)*(1-interval_width) + w*prediction``
      with the prediction flipped to ``1-p`` when the base prediction is
      <= 0.5 (classification and thresholded regression), then
      ``rank_features(width=score)``.

    ``rank_features`` and ``calculate_metrics`` are CE's public, documented
    ranking implementations; no local re-implementation is kept, so ordering
    (including NaN/inf coercion and tie behaviour) cannot drift from CE.
    ``rank_features`` returns ascending order; CE reverses it so the highest
    score is displayed first.

    Missing values are coerced the same way CE's plot path would receive them
    from the rules payload: absent weights/predictions become 0.0 and an
    absent interval bound yields a 0.0 width contribution.
    """
    if not items:
        return []

    import numpy as np  # noqa: PLC0415
    from calibrated_explanations.explanations.explanation import (  # noqa: PLC0415
        CalibratedExplanation,
    )
    from calibrated_explanations.utils.helper import calculate_metrics  # noqa: PLC0415

    n = len(items)
    rank_fn = getattr(local_explanation, "rank_features", None)
    if not callable(rank_fn):
        # ``CalibratedExplanation.rank_features`` never touches ``self``;
        # calling the public CE implementation unbound keeps CE authoritative
        # even for explanation payloads that don't subclass it.
        def rank_fn(feature_weights=None, width=None, num_to_show=None):  # type: ignore[misc]
            return CalibratedExplanation.rank_features(
                local_explanation,
                feature_weights=feature_weights,
                width=width,
                num_to_show=num_to_show,
            )

    if rnk_metric == "feature_weight":
        weights = np.array(
            [_as_float(item.get("weight")) or 0.0 for item in items], dtype=float
        )
        widths = np.array(
            [
                (_as_float(item.get("weight_high")) or 0.0)
                - (_as_float(item.get("weight_low")) or 0.0)
                for item in items
            ],
            dtype=float,
        )
        order = rank_fn(feature_weights=weights, width=widths, num_to_show=n)
    else:
        prediction = [_as_float(item.get("predict")) or 0.0 for item in items]
        # CE core: "Always rank base on predicted class" — flip when the base
        # prediction is <= 0.5 for classification or thresholded regression.
        if is_classification and base_predict is not None and base_predict <= 0.5:
            prediction = [1.0 - p for p in prediction]
        uncertainty = [
            (_as_float(item.get("predict_high")) or 0.0)
            - (_as_float(item.get("predict_low")) or 0.0)
            for item in items
        ]
        ranking = calculate_metrics(
            uncertainty=uncertainty,
            prediction=prediction,
            w=rnk_weight,
            metric=rnk_metric,
        )
        order = rank_fn(width=np.asarray(ranking, dtype=float), num_to_show=n)

    indices = list(order.tolist() if hasattr(order, "tolist") else order)
    indices.reverse()
    return [items[i] for i in indices]


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

        weight = _as_float(_sequence_get(rules.get("weight", ()), i))
        weight_low = _as_float(_sequence_get(rules.get("weight_low", ()), i))
        weight_high = _as_float(_sequence_get(rules.get("weight_high", ()), i))

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
                "weight": weight,
                "weight_low": weight_low,
                "weight_high": weight_high,
                "value": raw_value,
                "feature_names": feature_names,
                "feature_values": feature_values,
            }
        )

    return items


def _filter_identical_to_base(
    items: list[dict[str, Any]],
    base_predict: float | None,
    base_low: float | None,
    base_high: float | None,
) -> list[dict[str, Any]]:
    """Remove alternatives whose prediction+interval exactly match the base.

    Called after ranking and filter_top slicing to mirror CE core's order of operations:
    rank → filter_top → drop identical-to-base rows.
    """
    if base_predict is None or base_low is None or base_high is None:
        return list(items)

    import numpy as np  # noqa: PLC0415

    result = []
    for item in items:
        predict = _as_float(item.get("predict"))
        low = _as_float(item.get("predict_low"))
        high = _as_float(item.get("predict_high"))
        # CE core drops rows via np.isclose (rtol=1e-5, atol=1e-8) on all
        # three values; keep the identical tolerances for ordering parity.
        if (
            predict is None
            or low is None
            or high is None
            or not (
                np.isclose(predict, base_predict)
                and np.isclose(low, base_low)
                and np.isclose(high, base_high)
            )
        ):
            result.append(item)
    return result


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
        "version": PACKAGE_VERSION,
        "provider": PROVIDER,
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "intent": "alternative",
        "output_formats": ("html",),
        "capabilities": ["plot:builder"],
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

        # Thresholded regression renders as probabilistic in CE core (pivot=0.5, xlim=[0,1])
        is_thresholded_fn = getattr(local_explanation, "is_thresholded", None)
        is_thresholded = bool(is_thresholded_fn() if callable(is_thresholded_fn) else False)
        if is_regression and is_thresholded:
            is_regression = False

        pred_header = dict(getattr(local_explanation, "prediction", {}) or {})
        base_predict = _as_float(pred_header.get("predict", pred_header.get("prediction")))
        base_low = _as_float(pred_header.get("low", pred_header.get("predict_low")))
        base_high = _as_float(pred_header.get("high", pred_header.get("predict_high")))

        collection = _collection_for(local_explanation)

        # y_minmax for regression x-range.
        # y_minmax is set on the local explanation in CalibratedExplanation.__init__;
        # _collection_for() returns the parent CalibratedExplanations which does not carry it.
        y_minmax: list[float] | None = None
        y_minmax_raw = getattr(local_explanation, "y_minmax", None) or getattr(
            collection, "y_minmax", None
        )
        if y_minmax_raw is not None:
            try:
                y_minmax = [float(y_minmax_raw[0]), float(y_minmax_raw[1])]
            except (TypeError, IndexError, ValueError):
                y_minmax = None

        # Confidence level for the regression axis label — attribute access,
        # then get_confidence(). Only meaningful (and only safe to call) for
        # regression: CE's get_confidence() asserts low_high_percentiles,
        # which classification collections never set.
        conf_raw = getattr(collection, "confidence_level", None) or getattr(
            collection, "confidence", None
        )
        if conf_raw is None and is_regression:
            get_conf_fn = getattr(collection, "get_confidence", None)
            if callable(get_conf_fn):
                with contextlib.suppress(TypeError, ValueError, AttributeError):
                    conf_raw = get_conf_fn()
        confidence_pct = 95
        if conf_raw is not None:
            f_conf = _as_float(conf_raw)
            if f_conf is not None:
                confidence_pct = round(f_conf * 100) if f_conf <= 1.0 else int(f_conf)

        # Class label / threshold label for probabilistic x-axis label
        pred_label = None
        threshold_val = getattr(local_explanation, "threshold", None)
        if not is_regression and not is_thresholded:
            pred_header_dict = dict(getattr(local_explanation, "prediction", {}) or {})
            pred_label = pred_header_dict.get(
                "classes", pred_header_dict.get("class", pred_header_dict.get("label"))
            )
            if pred_label is None:
                get_cls_fn = getattr(local_explanation, "get_class_labels", None) or getattr(
                    collection, "get_class_labels", None
                )
                if callable(get_cls_fn):
                    with contextlib.suppress(
                        TypeError, ValueError, AttributeError, IndexError, KeyError
                    ):
                        _raw_cls = get_cls_fn()
                        if isinstance(_raw_cls, (list, tuple)) and len(_raw_cls) >= 2:
                            pred_label = _raw_cls[1]

        items = _extract_items(local_explanation, rules)

        # Rank, slice to filter_top, then drop identical-to-base (matches CE core order)
        items = _rank_items(
            items,
            rnk_metric=str(options["rnk_metric"]),
            rnk_weight=float(options["rnk_weight"]),
            base_predict=base_predict,
            is_classification=not is_regression,
            local_explanation=local_explanation,
        )
        if options["filter_top"] is not None:
            items = items[: int(options["filter_top"])]
        items = _filter_identical_to_base(items, base_predict, base_low, base_high)

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
                # Match PlotSpec build_alternative_regression_spec: use base prediction interval
                # bounds only; do not derive range from item intervals or add extra margin.
                base_bounds = [
                    v for v in (base_low, base_high)
                    if v is not None and math.isfinite(v)
                ]
                if base_bounds:
                    lo_b, hi_b = min(base_bounds), max(base_bounds)
                    if math.isclose(lo_b, hi_b, rel_tol=1e-9):
                        hi_b = lo_b + 1.0
                    xlim = [lo_b, hi_b]
                else:
                    xlim = [0.0, 1.0]
            pivot = None
            x_label = f"Prediction interval with {confidence_pct}% confidence"
            xticks = None
        else:
            xlim = [0.0, 1.0]
            pivot = 0.5
            if is_thresholded and threshold_val is not None:
                if isinstance(threshold_val, (list, tuple)) and len(threshold_val) == 2:
                    t0, t1 = float(threshold_val[0]), float(threshold_val[1])
                    x_label = (
                        f"Probability of target being between {t0:.3f} and {t1:.3f}"
                    )
                else:
                    thr_scalar = (
                        _as_float(threshold_val)
                        if not isinstance(threshold_val, (list, tuple))
                        else None
                    )
                    x_label = (
                        f"Probability of target being below {thr_scalar:.2f}"
                        if thr_scalar is not None
                        else f"Probability of target being below {threshold_val}"
                    )
            elif pred_label is not None:
                x_label = f"Probability for class '{pred_label}'"
            else:
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
                "rnk_metric": options["rnk_metric"],
                "rnk_weight": options["rnk_weight"],
            },
            "metadata": {
                "num_alternatives": len(items),
                "is_regression": is_regression,
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


# ── Renderer helpers ────────────────────────────────────────────────────────


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def _bar_color(predict: float | None, pivot: float | None, *, reduction: float = 0.99) -> str:
    """Interval bar fill color using the same legacy CE color function as PlotSpec/matplotlib."""
    if pivot is None:
        # Regression: PlotSpec renders IntervalSegment with alpha=0.4 → light-pink fill.
        # The full-opacity median marker must contrast against this background.
        return _hex_to_rgba(_REGRESSION_BAR_COLOR, 0.4)
    if predict is None:
        return _ce_fill_color(0.5, reduction)
    return _ce_fill_color(predict, reduction)


def _marker_color(predict: float | None, pivot: float | None) -> str:
    """Solid marker color for the prediction-point marker, full opacity."""
    if predict is None:
        return _ce_fill_color(0.5, 1.0)
    if pivot is None:
        return _REGRESSION_BAR_COLOR
    return _ce_fill_color(predict, 1.0)


def _title_for(artifact: PlotArtifact, options: dict[str, Any]) -> str:
    # No title for parity with CE legacy/PlotSpec behaviour (axis labels only).
    return ""


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

    show_y_labels = bool(render_options.get("show_y_labels", True))
    # show_rule_labels: controls the left-side rule-condition tick labels on the primary y-axis.
    # Defaults to show_y_labels so show_y_labels=False still hides everything (backward
    # compatible).
    show_rule_labels = bool(render_options.get("show_rule_labels", show_y_labels))
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
    predict_xs: list[float | None] = []
    marker_colors_list: list[str] = []

    # Segment data for interval bars (split at pivot when crossing, for probabilistic)
    # Each entry: (y_label, base, width, color, hover_text)
    seg_entries: list[tuple[str, float, float, str, str]] = []

    for y_label_item, item in zip(y_labels, items, strict=False):
        pred = _as_float(item.get("predict"))
        lo = _as_float(item.get("predict_low"))
        hi = _as_float(item.get("predict_high"))
        hover = str(item.get("hover", ""))

        # Replace infinities, then clamp to x-range
        if lo is not None:
            lo = x_lo if not math.isfinite(lo) else max(x_lo, min(x_hi, lo))
        if hi is not None:
            hi = x_hi if not math.isfinite(hi) else max(x_lo, min(x_hi, hi))

        predict_xs.append(pred)
        marker_colors_list.append(_marker_color(pred, pivot))

        if lo is None or hi is None:
            # No interval data — draw a zero-width bar at the prediction point
            p_x = pred if pred is not None else x_lo
            seg_entries.append((y_label_item, p_x, 0.0, _bar_color(pred, pivot), hover))
            continue

        if pivot is not None and lo < pivot < hi:
            # Split at the decision boundary: left side (pred < pivot) and right side
            seg_entries.append((y_label_item, lo, pivot - lo, _ce_fill_color(lo, 0.99), hover))
            seg_entries.append((y_label_item, pivot, hi - pivot, _ce_fill_color(hi, 0.99), hover))
        else:
            center = pred if pred is not None else (lo + hi) / 2
            seg_entries.append((y_label_item, lo, hi - lo, _bar_color(center, pivot), hover))

    fig = go.Figure()

    # ── 1. Base prediction interval background band ──────────────────────────
    if base_low is not None and base_high is not None:
        eff_lo = x_lo if not math.isfinite(base_low) else max(x_lo, base_low)
        eff_hi = x_hi if not math.isfinite(base_high) else min(x_hi, base_high)
        if eff_lo < eff_hi:
            if pivot is not None and eff_lo < pivot < eff_hi:
                # Split at the decision boundary using legacy CE colors (reduction=0.15)
                fig.add_vrect(
                    x0=eff_lo, x1=pivot,
                    fillcolor=_ce_fill_color(eff_lo, 0.15),
                    layer="below", line_width=0,
                )
                fig.add_vrect(
                    x0=pivot, x1=eff_hi,
                    fillcolor=_ce_fill_color(eff_hi, 0.15),
                    layer="below", line_width=0,
                )
            else:
                if is_regression:
                    band_color = _REGRESSION_BASE_COLOR
                else:
                    center = base_predict if base_predict is not None else (eff_lo + eff_hi) / 2
                    band_color = _ce_fill_color(center, 0.15)
                fig.add_vrect(
                    x0=eff_lo, x1=eff_hi,
                    fillcolor=band_color,
                    layer="below", line_width=0,
                )

    # ── 2. Regression: solid vertical line at base prediction (matching PlotSpec) ──────────────
    if is_regression and base_predict is not None:
        fig.add_vline(
            x=base_predict,
            line_width=2,
            line_color=_REGRESSION_BAR_COLOR,
            line_dash="solid",
            opacity=0.3,
        )

    # ── 3. Classification: dotted pivot line at 0.5 ─────────────────────────
    if pivot is not None:
        fig.add_vline(
            x=pivot,
            line_width=1,
            line_color="rgba(100,116,139,0.3)",
            line_dash="dot",
        )

    # ── 4. Interval bars: grouped by fill color for efficiency ──────────────
    # Bars may be split at the pivot for probabilistic plots (BARS-014).
    # Group by color so each distinct color is one go.Bar trace.
    color_groups: dict[str, list[tuple[str, float, float, str]]] = {}
    for y_lbl, base_v, width_v, color, hover in seg_entries:
        color_groups.setdefault(color, []).append((y_lbl, base_v, width_v, hover))

    for color, grp in color_groups.items():
        fig.add_trace(
            go.Bar(
                y=[e[0] for e in grp],
                x=[e[2] for e in grp],
                base=[e[1] for e in grp],
                orientation="h",
                width=0.4,
                marker={"color": color, "line": {"width": 0}},
                hovertext=[e[3] for e in grp],
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
                name="interval",
            )
        )

    # hover_texts for markers: one entry per item (not per segment)
    hover_texts_per_item = [str(item.get("hover", "")) for item in items]

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
            hovertext=hover_texts_per_item,
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
            name="prediction",
        )
    )

    # ── 6. Right-side instance values via secondary y-axis (PlotSpec twin-axis parity) ──────────
    n_items = len(items)
    instance_values_alt = [_display_value(item.get("value")) for item in items]

    # ── 7. Layout ────────────────────────────────────────────────────────────
    xaxis_cfg: dict[str, Any] = {
        "title": x_label,
        "range": [x_lo, x_hi],
    }
    if xticks is not None:
        xaxis_cfg["tickvals"] = xticks

    _margin = {
        "l": 5 if show_rule_labels else 10,
        "r": 110 if show_y_labels else 10,
        "t": 48,
        "b": 48,
    }
    fig.update_layout(
        template="plotly_white",
        title=_title_for(artifact, render_options),
        xaxis=xaxis_cfg,
        yaxis={
            "title": axis_meta.get("y_label", "Alternative rules"),
            "autorange": "reversed",
            "showticklabels": show_rule_labels,
            "automargin": True,
        },
        margin=_margin,
        showlegend=False,
        barmode="overlay",
        autosize=True,
    )
    if show_y_labels:
        # Secondary y-axis for instance values, overlaying primary.
        # Categorical labels map to integer indices 0..n-1; reversed primary puts index 0 at top.
        fig.update_layout(
            yaxis2={
                "overlaying": "y",
                "side": "right",
                "tickmode": "array",
                "tickvals": list(range(n_items)),
                "ticktext": instance_values_alt,
                "title": {"text": "Instance values", "font": {"size": 11}},
                "range": [n_items - 0.5, -0.5],
                "showgrid": False,
                "zeroline": False,
                "showline": False,
                "ticks": "",
            }
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
        "version": PACKAGE_VERSION,
        "provider": PROVIDER,
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
                "Install plotly (a mandatory dependency of "
                "calibrated-explanations-visualization-plotly); your "
                "environment appears to be missing or shadowing it."
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
    "LocalAlternativeBarsPlotBuilder",
    "LocalAlternativeBarsPlotRenderer",
    "build_figure",
]
