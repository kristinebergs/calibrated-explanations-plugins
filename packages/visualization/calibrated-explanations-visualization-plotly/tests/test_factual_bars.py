from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations import CalibratedExplainer
from calibrated_explanations.plugins.plots import PlotRenderContext
from sklearn.datasets import make_classification, make_regression
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split

STYLE_ID = "plotly.local.factual_bars"
BUILDER_ID = "official.visualization.plotly.local.factual_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.factual_bars.renderer"
BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"


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


def _trust_env() -> str:
    return ",".join(
        [
            "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
            BOOTSTRAP_ID,
            BUILDER_ID,
            RENDERER_ID,
        ]
    )


def _load_plugin(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


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


def _install_fake_plotly(monkeypatch):
    class FakeBar:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeScatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.vlines = []
            self.annotations = []
            self.layout = {}
            self.xaxes_updates = []
            self.yaxes_updates = []
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace, row=None, col=None):
            trace.kwargs["_row"] = row
            trace.kwargs["_col"] = col
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_vrect(self, **kwargs):
            self.vlines.append(kwargs)  # reuse vlines list; distinguishable via "x0"/"x1" keys

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **kwargs):
            self.xaxes_updates.append(kwargs)

        def update_yaxes(self, **kwargs):
            self.yaxes_updates.append(kwargs)

        def write_html(self, path, **_kwargs):
            self.html_paths.append(path)
            Path(path).write_text("<html></html>", encoding="utf-8")

        def show(self):
            self.shown = True

    def make_subplots(**kwargs):
        fig = FakeFigure()
        fig.layout["rows"] = kwargs.get("rows")
        fig.layout["subplot_titles"] = kwargs.get("subplot_titles")
        return fig

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Bar = FakeBar
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Figure = FakeFigure
    subplots_mod.make_subplots = make_subplots
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _rules() -> dict:
    return {
        "weight": [0.2, -0.5, 0.1, 0.4],
        "weight_low": [0.1, -0.8, -0.05, 0.3],
        "weight_high": [0.3, -0.2, 0.2, 0.6],
        "rule": ["b rule", "a rule", "d rule", "c rule"],
        "feature": [1, 0, 3, 2],
        "value": [20, 10, 40, 30],
        "feature_value": [20, 10, 40, 30],
    }


def _dummy_explanation(rules: dict | None = None, *, task="classification") -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income", "score", "risk"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81, "classes": 1},
        rules=rules or _rules(),
        get_mode=lambda: task,
        is_regression=lambda: task == "regression",
        is_probabilistic=lambda: task != "regression",
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": task, "mode": task}
    return collection


def test_registration_and_trusted_style_resolution(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    builder_descriptor = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_descriptor = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    assert builder_descriptor is not None
    assert builder_descriptor.trusted is True
    assert renderer_descriptor is not None
    assert renderer_descriptor.trusted is True
    assert style_descriptor is not None
    assert style_descriptor.metadata["builder_id"] == BUILDER_ID
    assert style_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


def test_default_artifact_options_and_hover_uncertainty(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), sort_by="original"))

    assert artifact["options_used"]["show_uncertainty"] is False
    assert artifact["options_used"]["hover_uncertainty"] is True
    hover = artifact["items"][0]["hover"]
    assert "Contribution interval: [0.1, 0.3]" in hover
    assert "Interval width: 0.2" in hover
    assert "Prediction interval: [0.66, 0.81]" in hover
    assert "Feature index: 1" in hover
    assert "Task: classification" in hover
    assert "Mode: classification" in hover


def test_renderer_no_header_has_single_bar_trace_and_zero_line(monkeypatch):
    """With show_prediction_header=False, single-row layout with one bar trace."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="original", show_prediction_header=False)
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    assert len(bar_traces) == 1
    assert result.figure.vlines[0]["x"] == 0
    assert result.figure is result.extras["figure"]
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


def test_renderer_with_prediction_header_uses_subplots(monkeypatch):
    """With show_prediction_header=True, a two-row subplot is created (header + body)."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="original", show_prediction_header=True)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    # Header row (all prediction bars) + body row = 2 total
    assert result.figure.layout.get("rows") == 2
    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    # 2 probability header bars × (solid + interval) = 4 header bars + 1 contribution bar
    assert len(bar_traces) >= 3
    assert result.figure is result.extras["figure"]


def test_missing_interval_metadata_does_not_crash(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "weight": [0.2, -0.1],
        "rule": ["age <= 42", "income > 10"],
        "feature": [0, 1],
        "feature_value": [37, 12],
    }
    context = _context(_dummy_explanation(rules), sort_by="original")

    result = plugin.render(plugin.build(context), context=context)

    assert result.artifact["metadata"]["num_missing_intervals"] == 2
    assert "Contribution interval: unavailable" in result.artifact["items"][0]["hover"]


def test_show_uncertainty_adds_visible_interval_trace(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), show_uncertainty=True, show_prediction_header=False)
    result = plugin.render(plugin.build(context), context=context)

    # Uncertainty intervals are now filled Bar traces (not Scatter lines).
    # Classification with a crossing-zero rule produces multiple color-grouped interval bars.
    interval_traces = [
        t for t in result.figure.traces
        if t.__class__.__name__ == "FakeBar" and t.kwargs.get("name") == "contribution interval"
    ]
    assert len(interval_traces) >= 1


def test_filter_top_limits_displayed_bars(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), filter_top=2, sort_by="abs"))

    assert len(artifact["items"]) == 2
    assert [item["rule"] for item in artifact["items"]] == ["a rule", "c rule"]


@pytest.mark.parametrize(
    ("sort_by", "expected"),
    [
        ("abs", ["a rule", "c rule", "b rule", "d rule"]),
        ("value", ["c rule", "b rule", "d rule", "a rule"]),
        ("interval_width", ["a rule", "c rule", "d rule", "b rule"]),
        ("label", ["a rule", "b rule", "c rule", "d rule"]),
        ("original", ["b rule", "a rule", "d rule", "c rule"]),
    ],
)
def test_sort_by_modes_are_deterministic(monkeypatch, sort_by, expected):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), sort_by=sort_by))

    assert [item["rule"] for item in artifact["items"]] == expected


def test_html_export_when_context_path_is_supplied(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    output_path = tmp_path / "local_factual_bars"
    context = _context(_dummy_explanation(), path=str(output_path))

    result = plugin.render(plugin.build(context), context=context)

    assert result.saved_paths == (str(output_path.with_suffix(".html")),)
    assert output_path.with_suffix(".html").exists()


def test_factual_classification_smoke_with_calibrated_explainer(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    features, labels = make_classification(
        n_samples=120,
        n_features=5,
        n_informative=3,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=0,
        stratify=labels,
    )
    model = LogisticRegression(random_state=0, solver="liblinear").fit(x_train, y_train)
    explanations = CalibratedExplainer(
        model,
        x_train,
        y_train,
        mode="classification",
        seed=0,
    ).explain_factual(x_test[:1])

    result = explanations.plot(style=STYLE_ID, show=False)

    assert result.artifact["artifact_type"] == STYLE_ID
    assert result.artifact["task"] == "classification"
    assert result.figure is result.extras["figure"]


def test_factual_regression_smoke_with_calibrated_explainer(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    features, target = make_regression(n_samples=120, n_features=4, noise=0.2, random_state=1)
    x_train, x_test, y_train, _ = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=0,
    )
    model = LinearRegression().fit(x_train, y_train)
    explanations = CalibratedExplainer(
        model,
        x_train,
        y_train,
        mode="regression",
        seed=0,
    ).explain_factual(x_test[:1])
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(explanations, filter_top=3)

    result = plugin.render(plugin.build(context), context=context)

    assert result.artifact["task"] == "regression"
    assert len(result.artifact["items"]) == 3


# ── Prediction header tests ───────────────────────────────────────────────────


def _dummy_regression_explanation() -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income", "score", "risk"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 42.5, "low": 38.2, "high": 46.8},
        rules=_rules(),
        get_mode=lambda: "regression",
        is_regression=lambda: True,
        is_probabilistic=lambda: False,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "regression", "mode": "regression"}
    return collection


def test_probabilistic_artifact_has_two_prediction_header_bars(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation()))

    pred = artifact["prediction"]
    assert pred["kind"] == "probabilistic"
    assert len(pred["bars"]) == 2
    assert pred["x_range"] == [0.0, 1.0]
    assert pred["x_label"] == "Probability"


def test_binary_complement_interval_is_1_minus_reversed(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation()))

    bars = artifact["prediction"]["bars"]
    target_bar = bars[0]
    complement_bar = bars[1]
    # Target: p=0.74, [0.66, 0.81]
    assert target_bar["value"] == pytest.approx(0.74)
    assert target_bar["low"] == pytest.approx(0.66)
    assert target_bar["high"] == pytest.approx(0.81)
    # Complement: 1-p=0.26, [1-0.81, 1-0.66] = [0.19, 0.34]
    assert complement_bar["value"] == pytest.approx(0.26)
    assert complement_bar["low"] == pytest.approx(1.0 - 0.81, abs=1e-6)
    assert complement_bar["high"] == pytest.approx(1.0 - 0.66, abs=1e-6)


def test_regression_artifact_has_one_prediction_header_bar(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_regression_explanation()))

    pred = artifact["prediction"]
    assert pred["kind"] == "regression"
    assert len(pred["bars"]) == 1
    assert pred["bars"][0]["label"] == "prediction"
    assert pred["bars"][0]["value"] == pytest.approx(42.5)
    assert pred["bars"][0]["low"] == pytest.approx(38.2)
    assert pred["bars"][0]["high"] == pytest.approx(46.8)
    assert pred["x_range"] is None
    # CE parity: regression header uses "Prediction interval [with X% confidence]"
    assert pred["x_label"].startswith("Prediction interval"), (
        f"Expected x_label to start with 'Prediction interval', got '{pred['x_label']}'"
    )


def test_show_prediction_header_false_suppresses_header_traces(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), show_prediction_header=False)

    result = plugin.render(plugin.build(context), context=context)

    # No subplots created when header is suppressed
    assert result.figure.layout.get("rows") is None
    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    assert len(bar_traces) == 1  # only contribution bars


def test_prediction_header_bars_included_in_renderer_output(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), show_prediction_header=True)

    result = plugin.render(plugin.build(context), context=context)

    # Header row (both probability bars together) + body row = 2 total
    assert result.figure.layout.get("rows") == 2
    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    # header: 2 probability bars (×2 traces each) + 1 contribution bar = ≥5
    assert len(bar_traces) >= 3


def test_regression_header_shows_one_bar_in_renderer(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_regression_explanation(), show_prediction_header=True)

    result = plugin.render(plugin.build(context), context=context)

    assert result.figure.layout.get("rows") == 2
    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    # header: 1 regression interval bar + 1 contribution bar = 2 minimum
    assert len(bar_traces) >= 2
    header_bars = [t for t in bar_traces if t.kwargs.get("_row") == 1]
    # Regression header: 1 interval bar (no solid portion from 0)
    assert len(header_bars) >= 1


def test_factual_bars_rejects_alternative_explanations(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    collection = SimpleNamespace(feature_names=["a"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={},
        rules={},
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]
    collection.batch_metadata = {}
    ctx = PlotRenderContext(
        explanation=collection,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({}),
    )
    with pytest.raises(ValueError, match="alternative"):
        plugin.build(ctx)


def test_contribution_bars_still_render_with_header_enabled(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="original", show_prediction_header=True)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    # Body is row 2 (header row 1 + body row 2)
    contribution_bars = [
        t for t in result.figure.traces
        if t.__class__.__name__ == "FakeBar" and t.kwargs.get("_row") == 2
    ]
    assert contribution_bars, "No contribution bar traces found on row 2"
    # The contribution bars use the same item count as the artifact
    assert len(contribution_bars[0].kwargs["y"]) == len(artifact["items"])


# ── New correctness tests ──────────────────────────────────────────────────────


def test_header_uses_three_part_structure_for_classification(monkeypatch):
    """Classification header must have solid + interval bars and markers, not a single 0→p bar."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), show_prediction_header=True, sort_by="original")
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    # Both probability bars are in row 1; each contributes solid + interval → ≥4 bar traces
    header_bars = [
        t for t in result.figure.traces
        if t.__class__.__name__ == "FakeBar" and t.kwargs.get("_row") == 1
    ]
    assert len(header_bars) >= 4, (
        f"Expected ≥4 header bar traces in row 1 (solid + interval per probability bar), "
        f"got {len(header_bars)}"
    )

    # Verify that some bars use 'base' (interval bars have non-zero base = p_low)
    bars_with_nonzero_base = [
        t for t in header_bars
        if t.kwargs.get("base") and any(b != 0 for b in t.kwargs["base"])
    ]
    assert bars_with_nonzero_base, (
        "Expected interval bars with non-zero base (p_low → p_high), but all bases were 0"
    )

    # Verify prediction markers appear in the header row
    header_markers = [
        t for t in result.figure.traces
        if t.__class__.__name__ == "FakeScatter" and t.kwargs.get("_row") == 1
    ]
    assert len(header_markers) >= 2, "Expected one marker trace per probability bar"


def test_regression_header_draws_interval_not_full_bar(monkeypatch):
    """Regression header must show interval from p_low to p_high, not a bar from 0 to p_val."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_regression_explanation(), show_prediction_header=True)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    header_bars = [
        t for t in result.figure.traces
        if t.__class__.__name__ == "FakeBar" and t.kwargs.get("_row") == 1
    ]
    assert header_bars, "No header bar traces found"

    interval_bar = header_bars[0]
    base_val = list(interval_bar.kwargs.get("base", [0.0]))[0]
    # The regression bar must start at p_low (38.2), not at 0
    assert base_val == pytest.approx(38.2), (
        f"Regression header bar starts at {base_val}, expected p_low=38.2"
    )
    # Width is p_high - p_low = 46.8 - 38.2 = 8.6
    x_val = list(interval_bar.kwargs["x"])[0]
    assert x_val == pytest.approx(8.6), (
        f"Regression header bar width is {x_val}, expected 8.6 (p_high - p_low)"
    )


def test_renderer_adds_right_axis_instance_value_annotations(monkeypatch):
    """Instance values must appear as right-side annotations on the body panel."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="original")
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    right_annotations = [
        a for a in result.figure.annotations
        if a.get("xref") == "paper" and a.get("x", 0) > 1.0
    ]
    assert len(right_annotations) >= len(artifact["items"]), (
        f"Expected ≥{len(artifact['items'])} right-side annotations for instance values, "
        f"got {len(right_annotations)}"
    )
    # Body is row 2 → annotations use yref="y2"
    assert any(a.get("yref") == "y2" for a in right_annotations), (
        "Body annotations should reference yref='y2' (body row) in 2-row layout"
    )


def test_uncertainty_suppresses_bars_that_cross_zero(monkeypatch):
    """When show_uncertainty=True, bars whose interval crosses zero must have value 0."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    # _rules() has: weight_low=[0.1, -0.8, -0.05, 0.3], weight_high=[0.3, -0.2, 0.2, 0.6]
    # Rule "d rule" (index 2): low=-0.05, high=0.2 → crosses zero
    context = _context(
        _dummy_explanation(),
        sort_by="original",
        show_uncertainty=True,
        show_prediction_header=False,
    )
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    assert bar_traces, "No bar traces"
    contribution_bar = bar_traces[0]
    x_vals = list(contribution_bar.kwargs["x"])
    y_vals = list(contribution_bar.kwargs["y"])

    # "d rule" (original index 2) crosses zero → bar value suppressed to 0.0
    d_rule_idx = y_vals.index("d rule")
    assert x_vals[d_rule_idx] == pytest.approx(0.0), (
        f"Bar for 'd rule' should be suppressed to 0 when interval crosses zero, "
        f"got {x_vals[d_rule_idx]}"
    )
    # "a rule" (original index 1): low=-0.8, high=-0.2 → does NOT cross zero → bar kept
    a_rule_idx = y_vals.index("a rule")
    assert x_vals[a_rule_idx] != pytest.approx(0.0), (
        "Bar for 'a rule' should NOT be suppressed — its interval doesn't cross zero"
    )


# ── CE core ranking parity ────────────────────────────────────────────────────


def test_default_ranking_uses_ce_feature_weight_order(monkeypatch):
    """Without explicit sort_by, builder must rank by abs(weight) with width tie-break
    — matching CE's rank_features(feature_weights, width=width) convention."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    # _rules(): weights=[0.2, -0.5, 0.1, 0.4], widths=[0.2, 0.6, 0.25, 0.3]
    # (|w|, width) pairs: (0.2,0.2), (0.5,0.6), (0.1,0.25), (0.4,0.3)
    # ascending sort: idx2, idx0, idx3, idx1 → reversed for display: [1,3,0,2]
    # rules at those indices: "a rule", "c rule", "b rule", "d rule"
    artifact = plugin.build(_context(_dummy_explanation()))

    rules_order = [item["rule"] for item in artifact["items"]]
    assert rules_order == ["a rule", "c rule", "b rule", "d rule"], (
        f"Expected CE feature_weight ranking order, got {rules_order}"
    )


def test_rnk_metric_and_rnk_weight_stored_in_options_used(monkeypatch):
    """rnk_metric and rnk_weight must appear in artifact options_used."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), rnk_metric="feature_weight", rnk_weight=0.3))

    assert artifact["options_used"]["rnk_metric"] == "feature_weight"
    assert artifact["options_used"]["rnk_weight"] == pytest.approx(0.3)


def test_uncertainty_rnk_metric_normalised_to_ensured(monkeypatch):
    """rnk_metric='uncertainty' must be normalised to 'ensured' with rnk_weight=1.0."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), rnk_metric="uncertainty"))

    assert artifact["options_used"]["rnk_metric"] == "ensured"
    assert artifact["options_used"]["rnk_weight"] == pytest.approx(1.0)


def test_explicit_sort_by_overrides_ce_ranking(monkeypatch):
    """Explicit sort_by must bypass CE ranking so legacy tests remain valid."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), sort_by="original"))

    rules_order = [item["rule"] for item in artifact["items"]]
    assert rules_order == ["b rule", "a rule", "d rule", "c rule"], (
        f"sort_by='original' must preserve insertion order, got {rules_order}"
    )


def test_filter_top_applies_to_ce_ranking(monkeypatch):
    """filter_top slices after CE ranking so the top-k by importance are kept."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # Default CE ranking: ["a rule", "c rule", "b rule", "d rule"]
    # filter_top=2 keeps the first two: ["a rule", "c rule"]
    artifact = plugin.build(_context(_dummy_explanation(), filter_top=2))

    rules_order = [item["rule"] for item in artifact["items"]]
    assert len(rules_order) == 2
    assert rules_order == ["a rule", "c rule"], (
        f"filter_top=2 with CE ranking must keep top-2 by importance, got {rules_order}"
    )


# ── One-sided uncertainty guard ───────────────────────────────────────────────


def test_one_sided_explanation_raises_warning_when_uncertainty_requested(monkeypatch):
    """Requesting show_uncertainty=True on a one-sided explanation must raise Warning,
    matching CE core behaviour (raise Warning(...))."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    collection = SimpleNamespace(feature_names=["a", "b"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81},
        rules=_rules(),
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
        is_one_sided=lambda: True,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}

    with pytest.raises(Warning, match="one-sided"):
        plugin.build(_context(collection, show_uncertainty=True))


def test_one_sided_explanation_without_uncertainty_does_not_raise(monkeypatch):
    """One-sided explanation without show_uncertainty must build without error."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    collection = SimpleNamespace(feature_names=["a", "b"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81},
        rules=_rules(),
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
        is_one_sided=lambda: True,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}

    artifact = plugin.build(_context(collection, show_uncertainty=False))

    assert artifact["artifact_type"] == STYLE_ID


# ── Regression confidence label ───────────────────────────────────────────────


def test_regression_header_label_uses_confidence_when_available(monkeypatch):
    """Regression header x_label must use 'Prediction interval with X% confidence'
    when get_confidence() is available on the collection."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    collection = SimpleNamespace(
        feature_names=["age", "income", "score", "risk"],
        get_confidence=lambda: 90,
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 42.5, "low": 38.2, "high": 46.8},
        rules=_rules(),
        get_mode=lambda: "regression",
        is_regression=lambda: True,
        is_probabilistic=lambda: False,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "regression", "mode": "regression"}

    artifact = plugin.build(_context(collection))

    assert artifact["prediction"]["x_label"] == "Prediction interval with 90% confidence"


def test_regression_header_label_fallback_without_confidence(monkeypatch):
    """Without get_confidence, regression header x_label must be 'Prediction interval'."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_regression_explanation()))

    assert artifact["prediction"]["x_label"] == "Prediction interval"
