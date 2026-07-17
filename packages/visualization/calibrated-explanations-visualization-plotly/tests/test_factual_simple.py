"""Tests for the plotly.local.factual_simple style.

The style replicates the client-side factual figure from the explainable-ai-hub
ExplainPage: horizontal weight bars in payload order, sign-based colouring,
optional error bars, compact fixed layout with transparent background.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest

pytest.importorskip("plotly")

from calibrated_explanations.plugins.plots import PlotRenderContext  # noqa: E402

STYLE_ID = "plotly.local.factual_simple"
BUILDER_ID = "official.visualization.plotly.local.factual_simple.builder"
RENDERER_ID = "official.visualization.plotly.local.factual_simple.renderer"
BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"

_POSITIVE_COLOR = "hsl(243,75%,59%)"
_NEGATIVE_COLOR = "hsl(0,84%,60%)"


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()
    clear_warnings = getattr(registry, "clear_trust_warnings", None)
    if callable(clear_warnings):
        clear_warnings()


def _load_plugin(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
                BOOTSTRAP_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _module(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    return importlib.import_module("ce_visualization_plotly.factual_simple")


def _context(explanation, *, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _rules() -> dict:
    return {
        "weight": [0.2, -0.5, 0.1, 0.4],
        "weight_low": [0.1, -0.8, -0.05, 0.3],
        "weight_high": [0.3, -0.2, 0.2, 0.6],
        "rule": [
            "b rule",
            "a rule",
            "a very long conjunctive rule condition that exceeds limits",
            "c rule",
        ],
        "feature": [1, 0, 3, 2],
        "value": [20, 10, 40, 30],
        "feature_value": [20, 10, 40, 30],
    }


def _dummy_explanation(rules: dict | None = None) -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income", "score", "risk"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81, "classes": 1},
        rules=rules or _rules(),
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


def test_style_is_registered(monkeypatch):
    _load_plugin(monkeypatch)
    descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    assert descriptor is not None
    metadata = getattr(descriptor, "metadata", descriptor)
    assert metadata.get("builder_id") == BUILDER_ID
    assert metadata.get("renderer_id") == RENDERER_ID


def test_builder_preserves_payload_order_and_truncates_labels(monkeypatch):
    module = _module(monkeypatch)
    builder = module.LocalFactualSimplePlotBuilder()
    artifact = builder.build(_context(_dummy_explanation()))

    items = artifact["items"]
    assert [item["rule"] for item in items] == _rules()["rule"]
    assert items[2]["name"] == _rules()["rule"][2][:30] + "…"
    assert items[0]["name"] == "b rule"
    assert [item["weight"] for item in items] == [0.2, -0.5, 0.1, 0.4]
    # error bars: distance from weight to interval bounds, floored at zero
    assert items[0]["error_low"] == pytest.approx(0.1)
    assert items[0]["error_high"] == pytest.approx(0.1)
    assert items[1]["error_low"] == pytest.approx(0.3)
    assert items[1]["error_high"] == pytest.approx(0.3)


def test_builder_skips_nan_and_none_weights(monkeypatch):
    module = _module(monkeypatch)
    rules = _rules()
    rules["weight"] = [0.2, None, float("nan"), 0.4]
    builder = module.LocalFactualSimplePlotBuilder()
    artifact = builder.build(_context(_dummy_explanation(rules)))
    assert [item["rule"] for item in artifact["items"]] == ["b rule", "c rule"]


def test_builder_rejects_alternative_explanations(monkeypatch):
    module = _module(monkeypatch)
    explanation = _dummy_explanation()
    explanation.explanations[0].is_alternative = lambda: True
    with pytest.raises(ValueError, match="does not support alternative"):
        module.LocalFactualSimplePlotBuilder().build(_context(explanation))


def test_builder_rejects_empty_rules(monkeypatch):
    module = _module(monkeypatch)
    rules = {key: [] for key in _rules()}
    with pytest.raises(ValueError, match="No factual rule contributions"):
        module.LocalFactualSimplePlotBuilder().build(_context(_dummy_explanation(rules)))


def test_figure_matches_hub_layout(monkeypatch):
    module = _module(monkeypatch)
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    context = _context(_dummy_explanation())
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)
    fig = result.figure

    assert len(fig.data) == 1
    bar = fig.data[0]
    assert bar.orientation == "h"
    assert list(bar.marker.color) == [
        _POSITIVE_COLOR,
        _NEGATIVE_COLOR,
        _POSITIVE_COLOR,
        _POSITIVE_COLOR,
    ]
    assert bar.hovertemplate == "%{y}<br>Weight: %{x:.4f}<extra></extra>"
    assert bar.error_x.visible is not True  # no error bars without show_uncertainty

    layout = fig.layout
    assert layout.margin.l == 10
    assert layout.margin.r == 20
    assert layout.margin.t == 10
    assert layout.margin.b == 40
    assert layout.xaxis.title.text == "Weight"
    assert layout.xaxis.zeroline is True
    assert layout.xaxis.zerolinewidth == 2
    assert layout.yaxis.automargin is True
    assert layout.yaxis.tickfont.size == 10
    assert layout.height == max(320, 4 * 40 + 80)
    assert layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert layout.plot_bgcolor == "rgba(0,0,0,0)"


def test_show_uncertainty_adds_error_bars(monkeypatch):
    module = _module(monkeypatch)
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    context = _context(_dummy_explanation(), show_uncertainty=True)
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)
    bar = result.figure.data[0]
    assert bar.error_x.visible is True
    assert list(bar.error_x.array) == pytest.approx([0.1, 0.3, 0.1, 0.2])
    assert list(bar.error_x.arrayminus) == pytest.approx([0.1, 0.3, 0.15, 0.1])


def test_height_floor_for_few_rules(monkeypatch):
    module = _module(monkeypatch)
    rules = {
        "weight": [0.2],
        "weight_low": [0.1],
        "weight_high": [0.3],
        "rule": ["b rule"],
        "feature": [1],
        "value": [20],
        "feature_value": [20],
    }
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    context = _context(_dummy_explanation(rules))
    result = renderer.render(builder.build(context), context=context)
    assert result.figure.layout.height == 320


def test_missing_plotly_produces_actionable_error(monkeypatch):
    module = _module(monkeypatch)

    def _raise_import_error(*args, **kwargs):
        raise ImportError("No module named 'plotly'")

    monkeypatch.setattr(module, "build_figure", _raise_import_error)
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    context = _context(_dummy_explanation())
    artifact = builder.build(context)
    with pytest.raises(RuntimeError, match="[Pp]lotly is required"):
        renderer.render(artifact, context=context)


def test_html_export_escapes_user_controlled_labels(monkeypatch, tmp_path):
    module = _module(monkeypatch)
    rules = _rules()
    rules["rule"] = [
        "<script>alert('xss')</script>",
        "f1 <= 0 & \"quoted\" 'label'",
        "ålder ≤ 40 × λ 日本語",
        "x" * 400,
    ]
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    out = tmp_path / "report.html"
    context = _context(_dummy_explanation(rules), path=str(out), show_uncertainty=True)
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)
    assert result.saved_paths == (str(out),)
    content = out.read_text(encoding="utf-8")
    assert "<script>alert(" not in content, (
        "user-controlled labels must not appear as executable HTML"
    )


def test_html_export(monkeypatch, tmp_path):
    module = _module(monkeypatch)
    builder = module.LocalFactualSimplePlotBuilder()
    renderer = module.LocalFactualSimplePlotRenderer()
    out = tmp_path / "figure.png"
    expected = tmp_path / "figure.html"
    context = _context(_dummy_explanation(), path=str(out))
    result = renderer.render(builder.build(context), context=context)
    assert result.saved_paths == (str(expected),)
    assert expected.exists()
    assert not out.exists()
