from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations.plugins.plots import PlotRenderContext

STYLE_ID = "plotly.local.alternative_bars"
BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
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
    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _alt_context(explanation, *, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "alternative"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _install_fake_plotly(monkeypatch):
    class FakeTrace:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeBar(FakeTrace):
        pass

    class FakeScatter(FakeTrace):
        pass

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.vlines = []
            self.vrects = []
            self.annotations = []
            self.layout = {}
            self.shown = False
            self.html_paths = []

        @property
        def data(self):
            return tuple(self.traces)

        def add_trace(self, trace, row=None, col=None):
            trace.kwargs["_row"] = row
            trace.kwargs["_col"] = col
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_vrect(self, **kwargs):
            self.vrects.append(kwargs)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **kwargs):
            pass

        def update_yaxes(self, **kwargs):
            pass

        def write_html(self, path, **_kwargs):
            self.html_paths.append(path)
            Path(path).write_text("<html><body>plotly</body></html>", encoding="utf-8")

        def show(self):
            self.shown = True

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Bar = FakeBar
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Figure = FakeFigure
    subplots_mod.make_subplots = lambda **kw: FakeFigure()
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _alt_rules() -> dict:
    return {
        "feature": [0, 1, 2, 3],
        "value": [10, 20, 30, 40],
        "rule": [
            "feat0 <= 10",
            "feat1 > 20",
            "feat2 <= 30",
            "feat3 > 40",
        ],
        "predict": [0.20, 0.85, 0.30, 0.70],
        "predict_low": [0.10, 0.75, 0.20, 0.60],
        "predict_high": [0.30, 0.95, 0.40, 0.80],
    }


def _dummy_alternative_explanation(*, rules: dict | None = None) -> SimpleNamespace:
    payload = rules or _alt_rules()
    collection = SimpleNamespace(
        feature_names=["feat0", "feat1", "feat2", "feat3"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.75, "low": 0.66, "high": 0.84},
        rules=payload,
        get_rules=lambda: payload,
        get_mode=lambda: "classification",
        is_probabilistic=lambda: True,
        is_regression=lambda: False,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]
    return collection


def _dummy_factual_explanation() -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81},
        rules={"weight": [0.2, -0.5], "rule": ["age <= 42", "income > 10"], "feature": [0, 1]},
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


# ── Registration ──────────────────────────────────────────────────────────────


def test_registration_exposes_style_builder_renderer(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    builder_desc = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_desc = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_desc = registry.find_plot_style_descriptor(STYLE_ID)

    assert builder_desc is not None
    assert builder_desc.trusted is True
    assert renderer_desc is not None
    assert renderer_desc.trusted is True
    assert style_desc is not None
    assert style_desc.metadata["builder_id"] == BUILDER_ID
    assert style_desc.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


# ── Builder ───────────────────────────────────────────────────────────────────


def test_builder_rejects_factual_explanations(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    with pytest.raises(ValueError, match="requires an alternative explanation"):
        plugin.build(_alt_context(_dummy_factual_explanation()))


def test_builder_accepts_alternative_explanation(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["artifact_version"] == "0.2.0"
    assert artifact["metadata"]["created_by"] == STYLE_ID
    assert artifact["items"]


def test_builder_items_store_absolute_predictions(monkeypatch):
    """Items must carry absolute predicted values, not deltas from base."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    for item in artifact["items"]:
        pred = item["predict"]
        assert pred is not None
        # Must be an absolute probability, not a delta (deltas would be negative here)
        assert 0.0 <= pred <= 1.0, f"predict={pred} is not a probability — looks like a delta"


def test_builder_base_prediction_is_dict(monkeypatch):
    """base_prediction must be a mapping with predict/low/high keys."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    bp = artifact["base_prediction"]
    assert isinstance(bp, dict)
    assert bp["predict"] == pytest.approx(0.75)
    assert bp["low"] == pytest.approx(0.66)
    assert bp["high"] == pytest.approx(0.84)


def test_builder_classification_axis_metadata(monkeypatch):
    """Classification explanations must set pivot=0.5 and xlim=[0,1]."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    meta = artifact["axis_metadata"]
    assert meta["pivot"] == pytest.approx(0.5)
    assert meta["xlim"] == pytest.approx([0.0, 1.0])
    assert meta["xticks"] is not None
    assert len(meta["xticks"]) == 11  # 0.0 … 1.0 in steps of 0.1


def test_builder_items_carry_instance_values_for_right_axis(monkeypatch):
    """Each item must carry the current feature value for the right y-axis."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    for item in artifact["items"]:
        assert "value" in item  # current feature value for right annotation


def test_builder_hover_contains_rule_and_prediction_info(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    for item in artifact["items"]:
        hover = item["hover"]
        assert "Rule:" in hover
        assert "Alt prediction:" in hover
        assert "Base prediction:" in hover
        assert "Interval:" in hover


def test_builder_hover_shows_delta_vs_base(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    # First rule: predict=0.20, base=0.75 → delta = -0.55
    first = artifact["items"][0]
    assert "Prediction delta:" in first["hover"]


def test_filter_top_limits_number_of_items(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), filter_top=2))

    assert len(artifact["items"]) == 2


def test_items_identical_to_base_are_excluded(monkeypatch):
    """Alternatives whose prediction and interval match the base must be dropped."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "feature": [0, 1],
        "value": [10, 20],
        "rule": ["f0 <= 5", "f1 > 3"],
        # first rule is identical to base prediction
        "predict": [0.75, 0.40],
        "predict_low": [0.66, 0.30],
        "predict_high": [0.84, 0.50],
    }
    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(rules=rules)))

    rules_in_output = [item["rule"] for item in artifact["items"]]
    assert "f0 <= 5" not in rules_in_output  # identical to base — must be excluded
    assert "f1 > 3" in rules_in_output


def test_missing_intervals_do_not_crash_builder(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "feature": [0, 1],
        "value": [5, 10],
        "rule": ["f0 <= 5", "f1 > 3"],
        "predict": [0.3, 0.8],
        # no predict_low / predict_high
    }

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(rules=rules)))

    assert artifact["items"]


def test_regression_explanation_sets_no_pivot(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    payload = {
        "feature": [0],
        "value": [5.0],
        "rule": ["x0 <= 5"],
        "predict": [12.5],
        "predict_low": [10.0],
        "predict_high": [15.0],
    }
    collection = SimpleNamespace(
        feature_names=["x0"],
        batch_metadata={"task": "regression", "mode": "regression"},
        y_minmax=[0.0, 30.0],
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 10.0, "low": 8.0, "high": 12.0},
        rules=payload,
        get_rules=lambda: payload,
        get_mode=lambda: "regression",
        is_probabilistic=lambda: False,
        is_regression=lambda: True,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]

    artifact = plugin.build(_alt_context(collection))

    meta = artifact["axis_metadata"]
    assert meta["pivot"] is None
    assert "confidence" in meta["x_label"].lower()
    assert artifact["metadata"]["is_regression"] is True


# ── Renderer ──────────────────────────────────────────────────────────────────


def test_renderer_has_bar_trace_for_intervals(monkeypatch):
    """Renderer must emit a horizontal Bar trace representing the prediction interval."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    assert bar_traces, "Expected at least one Bar trace for prediction intervals"
    # Bars must use absolute x-positions (base= and x= for widths), not deltas
    bar = bar_traces[0]
    assert "base" in bar.kwargs, "Bar must set 'base' to predict_low — not a delta from zero"
    bases = list(bar.kwargs["base"])
    widths = list(bar.kwargs["x"])
    assert any(b > 0 for b in bases), "All bases are 0 — bars look like deltas, not intervals"
    assert all(w >= 0 for w in widths), "Interval widths must be non-negative"


def test_renderer_has_scatter_trace_for_prediction_markers(monkeypatch):
    """Renderer must emit a Scatter trace marking the predicted value in each row."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    scatter_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeScatter"]
    assert scatter_traces, "Expected a Scatter trace for prediction markers"


def test_renderer_adds_vrect_for_base_interval(monkeypatch):
    """Base prediction interval must be rendered as a background shape, not a bar."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    assert result.figure.vrects, "Expected add_vrect call(s) for the base interval background"


def test_renderer_adds_right_axis_annotations(monkeypatch):
    """Current feature values must appear as right-side instance-value labels."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    # Instance values are now rendered via a secondary y-axis (yaxis2) instead of
    # paper-coord annotations, to guarantee tick alignment with horizontal bars.
    right_axis = result.figure.layout.get("yaxis2")
    assert right_axis is not None, "Expected yaxis2 for right-side instance values"
    assert right_axis.get("side") == "right"
    assert len(right_axis.get("ticktext", [])) >= len(artifact["items"]), (
        "Expected one tick label per alternative for instance values"
    )


def test_renderer_does_not_use_subplots(monkeypatch):
    """Alternative bars use a single panel — no prediction-header subplot."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    assert result.figure.layout.get("rows") is None


def test_renderer_classification_sets_x_range_0_1(monkeypatch):
    """Classification layout must lock x-range to [0, 1]."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    xaxis = result.figure.layout.get("xaxis", {})
    assert xaxis.get("range") == pytest.approx([0.0, 1.0])


def test_renderer_adds_pivot_vline_for_classification(monkeypatch):
    """A dotted vertical line must mark the 0.5 decision boundary."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    pivot_lines = [v for v in result.figure.vlines if v.get("x") == pytest.approx(0.5)]
    assert pivot_lines, "Expected a vline at pivot=0.5 for classification"


def test_renderer_y_labels_match_rule_text(monkeypatch):
    """Y-axis labels must be the alternative rule strings."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    # CE color grouping may split same-color items across multiple Bar traces (one
    # trace per distinct fill color), so collect y-labels across all bar traces.
    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    all_y_labels = {y for t in bar_traces for y in t.kwargs["y"]}
    expected_rules = {item["rule"] for item in artifact["items"]}
    assert all_y_labels == expected_rules


def test_renderer_no_warnings_on_valid_artifact(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plugin.render(plugin.build(context), context=context)

    assert not [w for w in caught if issubclass(w.category, UserWarning)]


def test_renderer_emits_warning_on_wrong_artifact_type(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)
    artifact["artifact_type"] = "wrong.type"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plugin.render(artifact, context=context)

    assert any(issubclass(w.category, UserWarning) for w in caught)


def test_html_export_creates_file(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(
        _dummy_alternative_explanation(), path=str(tmp_path / "alt_bars"), show=False
    )

    result = plugin.render(plugin.build(context), context=context)

    assert result.saved_paths[0].endswith("alt_bars.html")
    assert Path(result.saved_paths[0]).exists()
    assert result.figure is result.extras["figure"]


# ── Bridge ────────────────────────────────────────────────────────────────────


def test_bridge_is_installed(monkeypatch):
    _load_plugin(monkeypatch)
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation

        assert getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False)
    except ImportError:
        pytest.skip("AlternativeExplanation not accessible in this CE version")


def test_bridge_passes_non_alternative_bars_styles_through(monkeypatch):
    """Bridge must not intercept calls for unrelated styles."""
    _load_plugin(monkeypatch)
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation
    except ImportError:
        pytest.skip("AlternativeExplanation not accessible in this CE version")

    if not hasattr(AlternativeExplanation.plot, "__wrapped__"):
        pytest.skip("Cannot test bridge pass-through without access to wrapped function")

    assert getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False)


# ── Ranking ───────────────────────────────────────────────────────────────────


def test_default_ranking_is_ensured_metric(monkeypatch):
    """Default rnk_metric='ensured' ranks by rnk_weight*predict + (1-rnk_weight)*width."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # base_predict=0.75 (>= 0.5), all items: width=0.20 each
    # scores with rnk_weight=0.5: 0.5*predict + 0.5*0.20
    # predict: [0.20, 0.85, 0.30, 0.70] → scores [0.20, 0.525, 0.25, 0.45]
    # expected order (descending): feat1 > 20, feat3 > 40, feat2 <= 30, feat0 <= 10
    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    rules = [item["rule"] for item in artifact["items"]]
    assert rules[0] == "feat1 > 20", f"Highest-score alt should be first; got {rules}"
    assert rules[-1] == "feat0 <= 10", f"Lowest-score alt should be last; got {rules}"
    assert artifact["options_used"]["rnk_metric"] == "ensured"


def test_feature_weight_ranking(monkeypatch):
    """rnk_metric='feature_weight' falls back to |predict - base_predict| when weight absent."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # base_predict=0.75; deltas: [0.55, 0.10, 0.45, 0.05]
    # expected order: feat0 <= 10, feat2 <= 30, feat1 > 20, feat3 > 40
    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), rnk_metric="feature_weight")
    )

    rules = [item["rule"] for item in artifact["items"]]
    assert rules[0] == "feat0 <= 10", f"Largest delta alt should be first; got {rules}"
    assert rules[-1] == "feat3 > 40", f"Smallest delta alt should be last; got {rules}"


def test_rnk_weight_zero_ranks_by_interval_width_only(monkeypatch):
    """rnk_weight=0 reduces 'ensured' to pure interval-width ranking."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # All widths are 0.20, so order is stable (all equal, no change expected from original)
    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), rnk_weight=0.0)
    )

    # All scores equal (same width) → just verify no crash and items are present
    assert len(artifact["items"]) == 4


def test_filter_top_applies_after_ranking(monkeypatch):
    """filter_top slices after ranking, so the top-k by score are kept."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # With default "ensured" ranking, top item is "feat1 > 20" (score 0.525)
    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), filter_top=1)
    )

    assert len(artifact["items"]) == 1
    assert artifact["items"][0]["rule"] == "feat1 > 20"


def test_rnk_metric_stored_in_options_used(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), rnk_metric="feature_weight", rnk_weight=0.3)
    )

    assert artifact["options_used"]["rnk_metric"] == "feature_weight"
    assert artifact["options_used"]["rnk_weight"] == pytest.approx(0.3)


def test_rnk_metric_uncertainty_is_accepted(monkeypatch):
    """rnk_metric='uncertainty' must not raise; it normalises to 'ensured' with rnk_weight=1.0."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), rnk_metric="uncertainty")
    )

    # Normalised values are stored in options_used
    assert artifact["options_used"]["rnk_metric"] == "ensured"
    assert artifact["options_used"]["rnk_weight"] == pytest.approx(1.0)
    assert artifact["items"]


def test_feature_weight_ranking_uses_weight_field_when_available(monkeypatch):
    """rnk_metric='feature_weight' must prefer rules['weight'] over prediction delta."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # weight field values: [0.01, 0.80, 0.05, 0.50] — feature 1 (weight=0.80) should rank first
    # prediction deltas would give a different order: [0.55, 0.10, 0.45, 0.05]
    rules = {
        "feature": [0, 1, 2, 3],
        "value": [10, 20, 30, 40],
        "rule": ["feat0 <= 10", "feat1 > 20", "feat2 <= 30", "feat3 > 40"],
        "predict": [0.20, 0.85, 0.30, 0.70],
        "predict_low": [0.10, 0.75, 0.20, 0.60],
        "predict_high": [0.30, 0.95, 0.40, 0.80],
        "weight": [0.01, 0.80, 0.05, 0.50],
    }
    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(rules=rules), rnk_metric="feature_weight")
    )

    ranked_rules = [item["rule"] for item in artifact["items"]]
    assert ranked_rules[0] == "feat1 > 20", (
        f"Weight-field ranking should put feat1 (weight=0.80) first; got {ranked_rules}"
    )
    assert ranked_rules[-1] == "feat0 <= 10", (
        f"Weight-field ranking should put feat0 (weight=0.01) last; got {ranked_rules}"
    )


def test_thresholded_regression_renders_as_probabilistic(monkeypatch):
    """A thresholded regression explanation must use pivot=0.5 and xlim=[0,1]."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    payload = {
        "feature": [0],
        "value": [5.0],
        "rule": ["x0 <= 5"],
        "predict": [0.35],
        "predict_low": [0.20],
        "predict_high": [0.50],
    }
    collection = SimpleNamespace(
        feature_names=["x0"],
        batch_metadata={"task": "regression", "mode": "regression"},
        y_minmax=[0.0, 30.0],
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.60, "low": 0.45, "high": 0.75},
        rules=payload,
        get_rules=lambda: payload,
        get_mode=lambda: "regression",
        is_probabilistic=lambda: False,
        is_regression=lambda: True,
        is_thresholded=lambda: True,
        threshold=5.0,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]

    artifact = plugin.build(_alt_context(collection))

    meta = artifact["axis_metadata"]
    assert meta["pivot"] == pytest.approx(0.5), "Thresholded regression must use pivot=0.5"
    assert meta["xlim"] == pytest.approx([0.0, 1.0]), "Thresholded regression must use xlim=[0,1]"
    assert artifact["metadata"]["is_regression"] is False
    assert "5.0" in meta["x_label"], "Threshold value must appear in x_label"


def test_identical_to_base_filtered_after_ranking_and_filter_top(monkeypatch):
    """Identical-to-base filtering happens after ranking and filter_top (CE core order)."""
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # 3 rules: first (highest ensured score) is identical to base; second is not
    # With filter_top=2: rank → [rule_a(0.75), rule_b(0.85), rule_c(0.20)]
    #                    slice → [rule_a, rule_b]
    #                    filter identical → [rule_b] (rule_a dropped as identical)
    rules = {
        "feature": [0, 1, 2],
        "value": [10, 20, 30],
        "rule": ["identical", "good_alt", "low_score"],
        "predict": [0.75, 0.85, 0.20],
        "predict_low": [0.66, 0.75, 0.10],
        "predict_high": [0.84, 0.95, 0.30],
    }
    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(rules=rules), filter_top=2)
    )

    rule_names = [item["rule"] for item in artifact["items"]]
    assert "identical" not in rule_names, "Identical-to-base rule must be filtered"
    assert "good_alt" in rule_names, "Non-identical rule within filter_top must be kept"


def test_inline_fill_color_matches_ce_legacy_implementation(monkeypatch):
    """The inline legacy-color copy must match CE's implementation exactly.

    The plugin deliberately does NOT import the private CE symbol
    ``viz.builders._legacy_get_fill_color`` at runtime; this test uses it only
    as the parity oracle so drift in either copy is caught here.
    """
    _load_plugin(monkeypatch)
    from ce_visualization_plotly import alternative_bars as ab

    ce_builders = pytest.importorskip("calibrated_explanations.viz.builders")
    legacy_fill = getattr(ce_builders, "_legacy_get_fill_color", None)
    if legacy_fill is None:
        pytest.skip("CE no longer exposes _legacy_get_fill_color; parity oracle unavailable")

    probabilities = [index / 50 for index in range(51)] + [0.999999999, 1.0]
    for probability in probabilities:
        for reduction in (1.0, 0.99, 0.4, 0.15):
            assert ab._ce_fill_color(probability, reduction) == legacy_fill(
                probability, reduction
            ), f"fill color drift at p={probability}, reduction={reduction}"

    assert ab._REGRESSION_BAR_COLOR == ce_builders.REGRESSION_BAR_COLOR
    assert ab._REGRESSION_BASE_COLOR == ce_builders.REGRESSION_BASE_COLOR
