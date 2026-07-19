"""Ranking parity for ``plotly.local.alternative_bars`` (parity ledger BARS-004).

The builder must reproduce ``AlternativeExplanation.plot`` ranking on CE 1.0.x
by calling CE's public ``rank_features`` / ``calculate_metrics``. Every
expected order below is hand-computed from the CE semantics:

* ``feature_weight``: descending |weight|, weight-interval width tie-break.
* ``ensured``: descending ``(1-w)*(1-interval_width) + w*p_eff`` where
  ``p_eff = 1-p`` when the base prediction is <= 0.5 for classification.
* ``uncertainty``: alias for ``ensured`` with ``rnk_weight=1.0``.
* pipeline order: rank -> filter_top -> drop identical-to-base
  (``np.isclose`` on predict/low/high).
"""

from __future__ import annotations

import math
from types import MappingProxyType, SimpleNamespace

from calibrated_explanations.plugins.plots import PlotRenderContext
from ce_visualization_plotly.alternative_bars import (
    STYLE_ID,
    LocalAlternativeBarsPlotBuilder,
)


def _context(explanation, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "alternative"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _explanation(
    rules: dict,
    *,
    base=(0.75, 0.66, 0.84),
    mode: str = "classification",
) -> SimpleNamespace:
    n = len(rules["rule"])
    payload = dict(rules)
    payload.setdefault("feature", list(range(n)))
    payload.setdefault("value", list(range(10, 10 + 10 * n, 10)))
    is_regression = mode == "regression"
    collection = SimpleNamespace(
        feature_names=[f"f{i}" for i in range(n)],
        batch_metadata={"task": mode, "mode": mode},
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": base[0], "low": base[1], "high": base[2]},
        rules=payload,
        get_rules=lambda: payload,
        get_mode=lambda: mode,
        is_probabilistic=lambda: not is_regression,
        is_regression=lambda: is_regression,
        is_alternative=lambda: True,
        y_minmax=[0.0, 100.0] if is_regression else None,
    )
    collection.explanations = [local]
    return collection


def _order(artifact) -> list[str]:
    return [item["rule"] for item in artifact["items"]]


def _build(explanation, **options):
    return LocalAlternativeBarsPlotBuilder().build(_context(explanation, **options))


# ---------------------------------------------------------------------------
# feature_weight metric
# ---------------------------------------------------------------------------


def test_feature_weight_orders_by_absolute_weight():
    rules = {
        "rule": ["a", "b", "c"],
        "predict": [0.2, 0.6, 0.9],
        "predict_low": [0.1, 0.5, 0.8],
        "predict_high": [0.3, 0.7, 1.0],
        "weight": [-0.55, 0.10, 0.30],
        "weight_low": [-0.6, 0.05, 0.25],
        "weight_high": [-0.5, 0.15, 0.35],
    }
    artifact = _build(_explanation(rules), rnk_metric="feature_weight")
    assert _order(artifact) == ["a", "c", "b"]


def test_feature_weight_breaks_equal_weight_ties_by_interval_width():
    # |weight| equal for all three; widths 0.30 > 0.20 > 0.10 decide the order.
    rules = {
        "rule": ["narrow", "wide", "mid"],
        "predict": [0.2, 0.6, 0.9],
        "predict_low": [0.1, 0.5, 0.8],
        "predict_high": [0.3, 0.7, 1.0],
        "weight": [0.4, -0.4, 0.4],
        "weight_low": [0.35, -0.55, 0.30],
        "weight_high": [0.45, -0.25, 0.50],
    }
    artifact = _build(_explanation(rules), rnk_metric="feature_weight")
    assert _order(artifact) == ["wide", "mid", "narrow"]


def test_feature_weight_nan_and_inf_weights_are_coerced_like_ce():
    # CE's rank_features nan_to_num's: NaN -> 0.0, +/-inf -> +/-float max.
    rules = {
        "rule": ["nan", "inf", "plain"],
        "predict": [0.2, 0.6, 0.9],
        "predict_low": [0.1, 0.5, 0.8],
        "predict_high": [0.3, 0.7, 1.0],
        "weight": [math.nan, math.inf, 0.5],
        "weight_low": [0.0, 0.0, 0.45],
        "weight_high": [0.0, 0.0, 0.55],
    }
    artifact = _build(_explanation(rules), rnk_metric="feature_weight")
    assert _order(artifact) == ["inf", "plain", "nan"]


# ---------------------------------------------------------------------------
# ensured metric and the uncertainty alias
# ---------------------------------------------------------------------------


_ENSURED_RULES = {
    "rule": ["low_p_wide", "high_p_narrow", "mid_p_mid"],
    "predict": [0.20, 0.90, 0.55],
    "predict_low": [0.05, 0.85, 0.45],
    "predict_high": [0.65, 0.95, 0.65],  # widths: 0.60, 0.10, 0.20
    "weight": [-0.55, 0.15, -0.20],
    "weight_low": [-0.6, 0.1, -0.25],
    "weight_high": [-0.5, 0.2, -0.15],
}


def test_ensured_base_above_half_prefers_high_prediction_and_narrow_interval():
    # base 0.75 > 0.5 -> no flip. Scores at w=0.5:
    # 0.5*(1-0.60)+0.5*0.20=0.30 ; 0.5*(1-0.10)+0.5*0.90=0.90 ;
    # 0.5*(1-0.20)+0.5*0.55=0.675
    artifact = _build(_explanation(_ENSURED_RULES), rnk_metric="ensured", rnk_weight=0.5)
    assert _order(artifact) == ["high_p_narrow", "mid_p_mid", "low_p_wide"]


def test_ensured_base_below_half_flips_prediction_direction():
    # base 0.25 <= 0.5 -> p_eff = 1-p. Scores at w=0.5:
    # 0.5*0.40+0.5*0.80=0.60 ; 0.5*0.90+0.5*0.10=0.50 ; 0.5*0.80+0.5*0.45=0.625
    artifact = _build(
        _explanation(_ENSURED_RULES, base=(0.25, 0.16, 0.34)),
        rnk_metric="ensured",
        rnk_weight=0.5,
    )
    assert _order(artifact) == ["mid_p_mid", "low_p_wide", "high_p_narrow"]


def test_ensured_base_exactly_half_flips_like_ce():
    # CE flips when base predict is *not* strictly greater than 0.5.
    artifact = _build(
        _explanation(_ENSURED_RULES, base=(0.5, 0.4, 0.6)),
        rnk_metric="ensured",
        rnk_weight=0.5,
    )
    assert _order(artifact) == ["mid_p_mid", "low_p_wide", "high_p_narrow"]


def test_ensured_weight_zero_ranks_by_narrow_interval_only():
    # w=0 -> score = 1-width: narrow first, wide last, prediction ignored.
    artifact = _build(_explanation(_ENSURED_RULES), rnk_metric="ensured", rnk_weight=0.0)
    assert _order(artifact) == ["high_p_narrow", "mid_p_mid", "low_p_wide"]


def test_ensured_weight_one_ranks_by_prediction_only():
    # w=1 -> score = p (base 0.75, no flip): 0.90 > 0.55 > 0.20.
    artifact = _build(_explanation(_ENSURED_RULES), rnk_metric="ensured", rnk_weight=1.0)
    assert _order(artifact) == ["high_p_narrow", "mid_p_mid", "low_p_wide"]


def test_uncertainty_alias_equals_ensured_with_weight_one():
    by_alias = _build(_explanation(_ENSURED_RULES), rnk_metric="uncertainty")
    by_ensured = _build(_explanation(_ENSURED_RULES), rnk_metric="ensured", rnk_weight=1.0)
    assert _order(by_alias) == _order(by_ensured)
    assert by_alias["options_used"]["rnk_metric"] == "ensured"
    assert by_alias["options_used"]["rnk_weight"] == 1.0


def test_ensured_regression_never_flips():
    # Regression: no flip regardless of base; w=1 -> pure prediction order.
    rules = {
        "rule": ["small", "large"],
        "predict": [5.0, 50.0],
        "predict_low": [4.0, 40.0],
        "predict_high": [6.0, 60.0],
        "weight": [-1.0, 2.0],
        "weight_low": [-1.5, 1.5],
        "weight_high": [-0.5, 2.5],
    }
    artifact = _build(
        _explanation(rules, base=(10.0, 8.0, 12.0), mode="regression"),
        rnk_metric="ensured",
        rnk_weight=1.0,
    )
    assert _order(artifact) == ["large", "small"]


def test_missing_intervals_rank_as_zero_width():
    # Absent bounds contribute width 0.0 -> best (1-width) at w=0.
    rules = {
        "rule": ["no_interval", "wide"],
        "predict": [0.6, 0.6],
        "predict_low": [None, 0.2],
        "predict_high": [None, 1.0],
        "weight": [0.1, 0.1],
        "weight_low": [0.05, 0.05],
        "weight_high": [0.15, 0.15],
    }
    artifact = _build(_explanation(rules), rnk_metric="ensured", rnk_weight=0.0)
    assert _order(artifact) == ["no_interval", "wide"]


# ---------------------------------------------------------------------------
# Pipeline order: rank -> filter_top -> drop identical-to-base
# ---------------------------------------------------------------------------


def test_filter_top_takes_top_ranked_before_identical_filtering():
    # Ranked order (w=0.5, base 0.75): high_p_narrow, mid_p_mid, low_p_wide.
    artifact = _build(
        _explanation(_ENSURED_RULES), rnk_metric="ensured", rnk_weight=0.5, filter_top=2
    )
    assert _order(artifact) == ["high_p_narrow", "mid_p_mid"]


def test_identical_to_base_rows_are_dropped_with_isclose_tolerance():
    # "same" matches base within np.isclose tolerances (CE core semantics);
    # the previous plugin behaviour (abs diff >= 1e-10 keeps the row) would
    # have kept it.
    rules = {
        "rule": ["same", "different"],
        "predict": [0.75 + 1e-9, 0.20],
        "predict_low": [0.66, 0.10],
        "predict_high": [0.84, 0.30],
        "weight": [0.0, -0.55],
        "weight_low": [0.0, -0.6],
        "weight_high": [0.0, -0.5],
    }
    artifact = _build(_explanation(rules))
    assert _order(artifact) == ["different"]


def test_identical_filter_runs_after_filter_top():
    # filter_top=1 keeps only the top-ranked row; if that row is identical to
    # the base it is then dropped, leaving an empty item list (CE order:
    # rank -> slice -> drop identical), rather than backfilling from below.
    rules = {
        "rule": ["identical_top", "worse"],
        "predict": [0.75, 0.20],
        "predict_low": [0.66, 0.10],
        "predict_high": [0.84, 0.30],
        "weight": [0.0, -0.55],
        "weight_low": [0.0, -0.6],
        "weight_high": [0.0, -0.5],
    }
    artifact = _build(
        _explanation(rules), rnk_metric="ensured", rnk_weight=1.0, filter_top=1
    )
    assert _order(artifact) == []
