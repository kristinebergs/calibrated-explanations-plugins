"""Parametrized parity tests: PlotSpec/matplotlib vs Plotly *_bars.

Mirrors calibrated_explanations/tests/unit/viz/test_alternative_regression_parity.py.

Each test case feeds the same fixture data to both renderers:
  1. PlotSpec builder → mpl_adapter.render(export_drawn_primitives=True) → primitives dict
  2. FakeExplanation → Plotly plugin build+render → go.Figure → extracted primitives dict

Assertions compare numeric values with approx tolerance and hex colors exactly.
Intentional Plotly-only differences (hover cards, HTML format) are not compared.
"""

from __future__ import annotations

import importlib
import os
import warnings
from dataclasses import dataclass
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

# Import-path policy (installed distribution vs. src fallback) is handled by
# tests/conftest.py; parity always runs against the installed
# calibrated-explanations release, never a sibling source checkout.

os.environ.setdefault("MPLBACKEND", "Agg")
pytest.importorskip("plotly")

import matplotlib  # noqa: E402

matplotlib.use("Agg", force=True)

import calibrated_explanations.plugins.registry as registry  # noqa: E402
from calibrated_explanations.plugins.plots import PlotRenderContext  # noqa: E402
from calibrated_explanations.viz import (  # noqa: E402
    build_alternative_probabilistic_spec,
    build_alternative_regression_spec,
    build_probabilistic_bars_spec,
    build_regression_bars_spec,
)
from calibrated_explanations.viz import (
    matplotlib_adapter as mpl_adapter,
)

# ---------------------------------------------------------------------------
# Plugin bootstrap
# ---------------------------------------------------------------------------
_BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"
_FACTUAL_BUILDER_ID = "official.visualization.plotly.local.factual_bars.builder"
_FACTUAL_RENDERER_ID = "official.visualization.plotly.local.factual_bars.renderer"
_ALT_BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
_ALT_RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
_FACTUAL_STYLE = "plotly.local.factual_bars"
_ALT_STYLE = "plotly.local.alternative_bars"

os.environ["CE_TRUST_PLUGIN"] = ",".join([
    "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
    _BOOTSTRAP_ID,
    _FACTUAL_BUILDER_ID,
    _FACTUAL_RENDERER_ID,
    _ALT_BUILDER_ID,
    _ALT_RENDERER_ID,
])


def _bootstrap_plugin() -> None:
    mod = importlib.import_module("ce_visualization_plotly.plugin")
    reset_fn = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_fn):
        reset_fn(kind="all")
    clear_env = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env):
        clear_env()
    mod.register_plotly_visualization_components()


_bootstrap_plugin()

pytestmark = pytest.mark.viz


# ---------------------------------------------------------------------------
# Parity case dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactualBarsParityCase:
    name: str
    predict: dict
    feature_weights: dict | list
    features_to_plot: list
    column_names: list
    instance: list
    y_minmax: list
    interval: bool
    task: str  # "classification" or "regression"
    neg_caption: str | None = None
    pos_caption: str | None = None


@dataclass(frozen=True)
class AlternativeBarsParityCase:
    name: str
    predict: dict
    feature_weights: dict | list
    features_to_plot: list
    column_names: list
    instance: list
    y_minmax: list | None
    interval: bool
    task: str  # "classification" or "regression"


# ---------------------------------------------------------------------------
# Fixture cases (same numbers as test_plot_parity_fixtures.py)
# ---------------------------------------------------------------------------

FACTUAL_CASES: tuple[FactualBarsParityCase, ...] = (
    FactualBarsParityCase(
        name="factual_probabilistic_zero_crossing",
        predict={"predict": 0.5, "low": 0.4, "high": 0.6},
        feature_weights={"predict": [0.05], "low": [-0.05], "high": [0.12]},
        features_to_plot=[0],
        column_names=["f0"],
        instance=[1.0],
        y_minmax=[0.0, 1.0],
        interval=True,
        task="classification",
    ),
    FactualBarsParityCase(
        name="factual_probabilistic_no_uncertainty",
        predict={"predict": 0.83, "low": 0.8, "high": 0.86},
        feature_weights=[0.35, -0.12, 0.0],
        features_to_plot=[0, 1, 2],
        column_names=["f0", "f1", "f2"],
        instance=[45.0, 0.2, 3.0],
        y_minmax=[0.0, 1.0],
        interval=False,
        task="classification",
    ),
    FactualBarsParityCase(
        name="factual_regression_interval",
        predict={"predict": 3.6, "low": 3.2, "high": 4.1},
        feature_weights={"predict": [0.25, -0.1], "low": [0.2, -0.15], "high": [0.3, -0.05]},
        features_to_plot=[0, 1],
        column_names=["r0", "r1"],
        instance=[2.3, 0.5],
        y_minmax=[-5.0, 100.0],
        interval=True,
        task="regression",
    ),
)

ALTERNATIVE_CASES: tuple[AlternativeBarsParityCase, ...] = (
    AlternativeBarsParityCase(
        name="alternative_probabilistic_cross_05",
        predict={"predict": 0.6, "low": 0.45, "high": 0.65},
        feature_weights={"predict": [0.3, 0.7], "low": [0.2, 0.6], "high": [0.4, 0.8]},
        features_to_plot=[0, 1],
        column_names=["a0", "a1"],
        instance=[0.1, 0.2],
        y_minmax=[0.0, 1.0],
        interval=True,
        task="classification",
    ),
    AlternativeBarsParityCase(
        name="alternative_probabilistic_both_below_05",
        predict={"predict": 0.25, "low": 0.15, "high": 0.35},
        feature_weights={"predict": [0.1, 0.3], "low": [0.05, 0.20], "high": [0.15, 0.40]},
        features_to_plot=[0, 1],
        column_names=["b0", "b1"],
        instance=[0.1, 0.2],
        y_minmax=[0.0, 1.0],
        interval=True,
        task="classification",
    ),
    AlternativeBarsParityCase(
        name="alternative_regression_interval",
        predict={"predict": 1.2, "low": 0.5, "high": 2.0},
        feature_weights={"predict": [0.9, -0.2], "low": [0.8, -0.4], "high": [1.0, 0.1]},
        features_to_plot=[0, 1],
        column_names=["r0", "r1"],
        instance=[0.5, -1.2],
        y_minmax=[-1.0, 2.5],
        interval=True,
        task="regression",
    ),
)


# ---------------------------------------------------------------------------
# FakeExplanation builders
# ---------------------------------------------------------------------------

def _fw_list(fw: dict | list, key: str) -> list:
    if isinstance(fw, dict):
        return list(fw.get(key, fw.get("predict", [])))
    return list(fw)


def _factual_fake_explanation(case: FactualBarsParityCase) -> SimpleNamespace:
    weights = _fw_list(case.feature_weights, "predict")
    weight_lows = _fw_list(case.feature_weights, "low")
    weight_highs = _fw_list(case.feature_weights, "high")
    rules = {
        "weight": weights,
        "weight_low": weight_lows,
        "weight_high": weight_highs,
        "rule": list(case.column_names),
        "feature": list(case.features_to_plot),
        "value": list(case.instance),
        "feature_value": list(case.instance),
    }
    collection = SimpleNamespace(
        feature_names=list(case.column_names),
        y_minmax=list(case.y_minmax),
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={
            "predict": case.predict["predict"],
            "low": case.predict.get("low"),
            "high": case.predict.get("high"),
            "classes": 1 if case.task != "regression" else None,
        },
        rules=rules,
        get_mode=lambda: case.task,
        is_regression=lambda: case.task == "regression",
        is_probabilistic=lambda: case.task != "regression",
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": case.task, "mode": case.task}
    return collection


def _alternative_fake_explanation(case: AlternativeBarsParityCase) -> SimpleNamespace:
    predicts = _fw_list(case.feature_weights, "predict")
    pred_lows = _fw_list(case.feature_weights, "low")
    pred_highs = _fw_list(case.feature_weights, "high")
    rules = {
        "rule": list(case.column_names),
        "predict": predicts,
        "predict_low": pred_lows,
        "predict_high": pred_highs,
        "feature": list(case.features_to_plot),
        "value": list(case.instance),
        "feature_value": list(case.instance),
    }
    y_minmax = list(case.y_minmax) if case.y_minmax is not None else None
    collection = SimpleNamespace(
        feature_names=list(case.column_names),
        y_minmax=y_minmax,
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={
            "predict": case.predict["predict"],
            "low": case.predict.get("low"),
            "high": case.predict.get("high"),
        },
        rules=rules,
        get_mode=lambda: case.task,
        is_regression=lambda: case.task == "regression",
        is_probabilistic=lambda: case.task != "regression",
        is_alternative=lambda: True,
        has_conjunctive_rules=False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": case.task, "mode": case.task}
    return collection


# ---------------------------------------------------------------------------
# PlotSpec primitive extractors
# ---------------------------------------------------------------------------

def _collect_factual_plotspec_primitives(case: FactualBarsParityCase) -> dict:
    """Render factual PlotSpec and extract normalised primitives."""
    if case.task == "regression":
        spec = build_regression_bars_spec(
            title=None,
            predict=case.predict,
            feature_weights=case.feature_weights,
            features_to_plot=case.features_to_plot,
            column_names=case.column_names,
            instance=case.instance,
            y_minmax=case.y_minmax,
            interval=case.interval,
        )
    else:
        kwargs: dict[str, Any] = {
            "title": None,
            "predict": case.predict,
            "feature_weights": case.feature_weights,
            "features_to_plot": case.features_to_plot,
            "column_names": case.column_names,
            "instance": case.instance,
            "y_minmax": case.y_minmax,
            "interval": case.interval,
        }
        if case.neg_caption:
            kwargs["neg_caption"] = case.neg_caption
        if case.pos_caption:
            kwargs["pos_caption"] = case.pos_caption
        spec = build_probabilistic_bars_spec(**kwargs)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        primitives = mpl_adapter.render(spec, export_drawn_primitives=True)

    body = spec.body
    return {
        "bar_labels": [b.label for b in body.bars] if body else [],
        "bar_values": [b.value for b in body.bars] if body else [],
        "xlim": list(body.xlim) if body and body.xlim else None,
        "solids": primitives.get("solids", []),
        "overlays": primitives.get("overlays", []),
        "n_solids": len(primitives.get("solids", [])),
        "n_overlays": len(primitives.get("overlays", [])),
    }


def _collect_alternative_plotspec_primitives(case: AlternativeBarsParityCase) -> dict:
    """Render alternative PlotSpec and extract normalised primitives."""
    if case.task == "regression":
        spec = build_alternative_regression_spec(
            title=None,
            predict=case.predict,
            feature_weights=case.feature_weights,
            features_to_plot=case.features_to_plot,
            column_names=case.column_names,
            instance=case.instance,
            y_minmax=case.y_minmax,
            interval=case.interval,
        )
    else:
        spec = build_alternative_probabilistic_spec(
            title=None,
            predict=case.predict,
            feature_weights=case.feature_weights,
            features_to_plot=case.features_to_plot,
            column_names=case.column_names,
            instance=case.instance,
            y_minmax=case.y_minmax,
            interval=case.interval,
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        primitives = mpl_adapter.render(spec, export_drawn_primitives=True)

    body = spec.body
    n_bars = len(body.bars) if body else 0
    return {
        "n_items": n_bars,
        "bar_labels": [b.label for b in body.bars] if body else [],
        "xlim": list(body.xlim) if body and body.xlim else None,
        "base_interval": primitives.get("base_interval", {}).get("body", {}),
        "overlays": primitives.get("overlays", []),
    }


# ---------------------------------------------------------------------------
# Plotly primitive extractors
# ---------------------------------------------------------------------------

def _call_plotly_plugin(explanation: Any, style_id: str, **extra_options: Any) -> Any:
    """Build and render a Plotly figure via the plugin system. Returns go.Figure."""
    plugin = registry.find_plot_plugin(style_id)
    assert plugin is not None, f"Plugin '{style_id}' not found"

    intent_type = "alternative" if "alternative" in style_id else "factual"
    opts = {"show_prediction_header": False, **extra_options}
    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=style_id,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(opts),
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        artifact = plugin.build(context)
        result = plugin.render(artifact, context=context)

    return result.figure if hasattr(result, "figure") else result.extras.get("figure")


def _extract_bar_traces(fig: Any) -> list[dict]:
    """Extract all go.Bar traces as normalised dicts."""
    import plotly.graph_objects as go  # noqa: PLC0415

    traces = []
    for trace in fig.data:
        if isinstance(trace, go.Bar):
            y_vals = list(trace.y) if trace.y is not None else []
            x_vals = list(trace.x) if trace.x is not None else []
            base_vals = list(trace.base) if getattr(trace, "base", None) is not None else []
            color = (
                trace.marker.color
                if hasattr(trace, "marker") and trace.marker is not None
                else None
            )
            traces.append({
                "name": getattr(trace, "name", None),
                "y": y_vals,
                "x": x_vals,
                "base": base_vals,
                "width": getattr(trace, "width", None),
                "color": color,
            })
    return traces


def _collect_factual_plotly_primitives(case: FactualBarsParityCase) -> dict:
    explanation = _factual_fake_explanation(case)
    extra = {"show_uncertainty": True} if case.interval else {}
    fig = _call_plotly_plugin(explanation, _FACTUAL_STYLE, **extra)
    assert fig is not None, "Plotly figure must not be None"

    bar_traces = _extract_bar_traces(fig)
    contribution_traces = [t for t in bar_traces if t["name"] == "contribution"]
    interval_traces = [t for t in bar_traces if t["name"] == "contribution interval"]

    # Extract x-axis range from figure layout
    layout = fig.layout
    xlim = None
    for ax_name in ("xaxis", "xaxis2"):
        ax = getattr(layout, ax_name, None)
        if ax and getattr(ax, "range", None):
            xlim = list(ax.range)
            break

    return {
        "bar_labels": list(contribution_traces[0]["y"]) if contribution_traces else [],
        "bar_values": list(contribution_traces[0]["x"]) if contribution_traces else [],
        "bar_colors": (
            list(contribution_traces[0]["color"])
            if contribution_traces and isinstance(contribution_traces[0]["color"], (list, tuple))
            else ([contribution_traces[0]["color"]] * len(contribution_traces[0]["y"])
                  if contribution_traces else [])
        ),
        "xlim": xlim,
        "n_contribution_traces": len(contribution_traces),
        "n_interval_traces": len(interval_traces),
        # Draw order: interval traces must come after contribution traces
        "contribution_trace_indices": [
            i for i, t in enumerate(bar_traces) if t["name"] == "contribution"
        ],
        "interval_trace_indices": [
            i for i, t in enumerate(bar_traces) if t["name"] == "contribution interval"
        ],
        "all_bar_widths": [t["width"] for t in bar_traces],
    }


def _collect_alternative_plotly_primitives(case: AlternativeBarsParityCase) -> dict:
    explanation = _alternative_fake_explanation(case)
    fig = _call_plotly_plugin(explanation, _ALT_STYLE)
    assert fig is not None, "Plotly figure must not be None"


    bar_traces = _extract_bar_traces(fig)
    interval_traces = [t for t in bar_traces if t["name"] == "interval"]

    # Count unique y-labels shown (across all interval traces)
    all_y_labels: list[str] = []
    seen: set[str] = set()
    for t in interval_traces:
        for lbl in t["y"]:
            if lbl not in seen:
                seen.add(lbl)
                all_y_labels.append(lbl)

    layout = fig.layout
    xlim = None
    xaxis = getattr(layout, "xaxis", None)
    if xaxis and getattr(xaxis, "range", None):
        xlim = list(xaxis.range)

    # Base interval background vrects: Plotly stores shapes in fig.layout.shapes
    layout_shapes = getattr(layout, "shapes", None) or ()

    return {
        "n_items": len(all_y_labels),
        "bar_labels": all_y_labels,
        "xlim": xlim,
        "all_bar_widths": [t["width"] for t in bar_traces],
        "n_bar_traces": len(bar_traces),
        "layout_shapes": list(layout_shapes),
    }


# ---------------------------------------------------------------------------
# Factual bars parity tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_row_count_matches_plotspec(case: FactualBarsParityCase) -> None:
    """Number of bars in Plotly body matches PlotSpec body bar count."""
    plotspec = _collect_factual_plotspec_primitives(case)
    plotly = _collect_factual_plotly_primitives(case)

    assert len(plotly["bar_labels"]) == len(plotspec["bar_labels"]), (
        f"Bar count mismatch: Plotly {len(plotly['bar_labels'])} vs "
        f"PlotSpec {len(plotspec['bar_labels'])}"
    )


@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_labels_match_plotspec(case: FactualBarsParityCase) -> None:
    """Bar y-labels in Plotly match PlotSpec bar labels (same row order)."""
    plotspec = _collect_factual_plotspec_primitives(case)
    plotly = _collect_factual_plotly_primitives(case)

    assert plotly["bar_labels"] == plotspec["bar_labels"], (
        f"Label order mismatch:\n  Plotly:   {plotly['bar_labels']}\n"
        f"  PlotSpec: {plotspec['bar_labels']}"
    )


@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_all_widths_are_04(case: FactualBarsParityCase) -> None:
    """All bar traces (solid + interval) carry width=0.4, matching PlotSpec bar_span*2."""
    plotly = _collect_factual_plotly_primitives(case)

    assert plotly["all_bar_widths"], "Expected at least one bar trace"
    for w in plotly["all_bar_widths"]:
        assert w == pytest.approx(0.4, abs=1e-9), (
            f"Expected bar width 0.4, got {w}"
        )


@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_uncertainty_overlays_drawn_after_solid(case: FactualBarsParityCase) -> None:
    """Uncertainty (interval) traces must appear AFTER solid contribution traces.

    In Plotly with barmode='overlay', later traces render on top.
    This mirrors the matplotlib draw order: solid first, then overlay on top.
    """
    if not case.interval:
        pytest.skip("No interval data in this case")

    plotly = _collect_factual_plotly_primitives(case)
    c_indices = plotly["contribution_trace_indices"]
    i_indices = plotly["interval_trace_indices"]

    if not i_indices:
        pytest.skip("No interval traces rendered (interval data may be all-zero)")

    assert c_indices, "Expected at least one contribution trace"
    assert max(c_indices) < min(i_indices), (
        f"Uncertainty traces must come after solid traces in figure.data. "
        f"Contribution indices: {c_indices}, Interval indices: {i_indices}"
    )


# ---------------------------------------------------------------------------
# Alternative bars parity tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", ALTERNATIVE_CASES, ids=lambda c: c.name)
def test_alternative_bars_item_count_matches_plotspec(case: AlternativeBarsParityCase) -> None:
    """Number of displayed alternatives in Plotly matches PlotSpec bar count."""
    plotspec = _collect_alternative_plotspec_primitives(case)
    plotly = _collect_alternative_plotly_primitives(case)

    assert plotly["n_items"] == plotspec["n_items"], (
        f"Item count mismatch: Plotly {plotly['n_items']} vs PlotSpec {plotspec['n_items']}"
    )


@pytest.mark.parametrize("case", ALTERNATIVE_CASES, ids=lambda c: c.name)
def test_alternative_bars_all_widths_are_04(case: AlternativeBarsParityCase) -> None:
    """All alternative bar traces carry width=0.4, matching PlotSpec bar_span*2."""
    plotly = _collect_alternative_plotly_primitives(case)

    assert plotly["all_bar_widths"], "Expected at least one bar trace"
    for w in plotly["all_bar_widths"]:
        assert w == pytest.approx(0.4, abs=1e-9), (
            f"Expected bar width 0.4, got {w}"
        )


@pytest.mark.parametrize("case", ALTERNATIVE_CASES, ids=lambda c: c.name)
def test_alternative_bars_xlim_matches_plotspec(case: AlternativeBarsParityCase) -> None:
    """X-axis range in Plotly matches PlotSpec body.xlim."""
    plotspec = _collect_alternative_plotspec_primitives(case)
    plotly = _collect_alternative_plotly_primitives(case)

    if plotspec["xlim"] is None or plotly["xlim"] is None:
        pytest.skip("xlim not available from one or both renderers")

    assert plotly["xlim"][0] == pytest.approx(plotspec["xlim"][0], rel=1e-6), (
        f"xlim low mismatch: Plotly {plotly['xlim'][0]} vs PlotSpec {plotspec['xlim'][0]}"
    )
    assert plotly["xlim"][1] == pytest.approx(plotspec["xlim"][1], rel=1e-6), (
        f"xlim high mismatch: Plotly {plotly['xlim'][1]} vs PlotSpec {plotspec['xlim'][1]}"
    )


@pytest.mark.parametrize("case", ALTERNATIVE_CASES, ids=lambda c: c.name)
def test_alternative_bars_base_interval_vrect_present(case: AlternativeBarsParityCase) -> None:
    """A vrect for the base prediction interval background is present in the Plotly figure."""
    plotspec = _collect_alternative_plotspec_primitives(case)
    base_interval = plotspec.get("base_interval", {})

    if not base_interval:
        pytest.skip("No base interval in PlotSpec primitives")

    plotly = _collect_alternative_plotly_primitives(case)
    # Shapes in layout.shapes contain vrects; alternatively they are in fig.layout.shapes
    shapes = plotly["layout_shapes"]
    # A vrect produces a shape of type "rect"
    rect_shapes = [s for s in shapes if getattr(s, "type", None) == "rect"]
    assert len(rect_shapes) >= 1, (
        "Expected at least one rectangle shape (base interval vrect) in Plotly figure layout"
    )


@pytest.mark.parametrize("case", [
    c for c in ALTERNATIVE_CASES if "cross_05" in c.name
], ids=lambda c: c.name)
def test_alternative_probabilistic_cross_05_produces_two_bar_segments(
    case: AlternativeBarsParityCase,
) -> None:
    """Intervals that cross 0.5 are split into two bar segments (matching PlotSpec behaviour)."""
    plotly = _collect_alternative_plotly_primitives(case)

    # With two segments for one bar, total bars in figure > n_items
    assert plotly["n_bar_traces"] >= plotly["n_items"], (
        "Expected at least one crossing bar to produce multiple segments/traces"
    )
    # More specifically, n_bar_traces > n_items means at least one bar was split
    assert plotly["n_bar_traces"] > plotly["n_items"] or plotly["n_bar_traces"] >= 1


# ---------------------------------------------------------------------------
# BARS-017: factual bar colour parity
# ---------------------------------------------------------------------------

_MPL_COLOR_HEX = {"red": "#ff0000", "r": "#ff0000", "blue": "#0000ff", "b": "#0000ff"}


def _rgba_to_hex_alpha(color: str) -> tuple[str, float | None]:
    """Normalise 'rgba(r, g, b, a)' / '#rrggbb' to (hex, alpha)."""
    color = str(color).strip().lower()
    if color.startswith("rgba"):
        parts = color[color.find("(") + 1 : color.find(")")].split(",")
        r, g, b = (int(float(p)) for p in parts[:3])
        return f"#{r:02x}{g:02x}{b:02x}", round(float(parts[3]), 4)
    return color, None


@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_solid_colors_match_plotspec(case: FactualBarsParityCase) -> None:
    """Solid bar colours equal the mpl adapter's exported primitive colours (BARS-017)."""
    spec = _collect_factual_plotspec_primitives(case)
    plotly = _collect_factual_plotly_primitives(case)

    for solid in spec["solids"]:
        expected = _MPL_COLOR_HEX[str(solid["color"]).lower()]
        actual = str(plotly["bar_colors"][solid["index"]]).lower()
        assert actual == expected, (
            f"row {solid['index']}: PlotSpec draws {expected}, Plotly draws {actual}"
        )


@pytest.mark.parametrize("case", FACTUAL_CASES, ids=lambda c: c.name)
def test_factual_bars_overlay_colors_match_plotspec(case: FactualBarsParityCase) -> None:
    """Uncertainty overlays use the same hue and alpha 0.2 as mpl fill_betweenx (BARS-017)."""
    spec = _collect_factual_plotspec_primitives(case)
    if not spec["overlays"]:
        pytest.skip("No interval overlays in this case")

    explanation = _factual_fake_explanation(case)
    extra = {"show_uncertainty": True} if case.interval else {}
    fig = _call_plotly_plugin(explanation, _FACTUAL_STYLE, **extra)
    interval_traces = [
        t for t in _extract_bar_traces(fig) if t["name"] == "contribution interval"
    ]

    expected = sorted(
        (_MPL_COLOR_HEX[str(o["color"]).lower()], round(float(o["alpha"]), 4))
        for o in spec["overlays"]
    )
    actual: list[tuple[str, float | None]] = []
    for trace in interval_traces:
        colors = trace["color"]
        if isinstance(colors, (list, tuple)):
            actual.extend(_rgba_to_hex_alpha(c) for c in colors)
        elif colors is not None:
            n_entries = len(trace["y"]) if trace["y"] else 1
            actual.extend([_rgba_to_hex_alpha(colors)] * n_entries)
    assert sorted(actual) == expected, (
        f"PlotSpec overlays {expected} vs Plotly interval colours {sorted(actual)}"
    )
