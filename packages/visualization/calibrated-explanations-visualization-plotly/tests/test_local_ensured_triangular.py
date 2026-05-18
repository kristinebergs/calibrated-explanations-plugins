from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations import WrapCalibratedExplainer
from calibrated_explanations.plugins.plots import PlotRenderContext
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

STYLE_ID = "plotly.local.ensured_triangular"
BUILDER_ID = "official.visualization.plotly.local.ensured_triangular.builder"
RENDERER_ID = "official.visualization.plotly.local.ensured_triangular.renderer"
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
        intent=MappingProxyType({"type": "alternative"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _install_fake_plotly(monkeypatch):
    class FakeScatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFigure:
        def __init__(self):
            self.traces = []
            self.annotations = []
            self.layout = {}
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace):
            self.traces.append(trace)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def write_html(self, path):
            self.html_paths.append(path)

        def show(self):
            self.shown = True

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    graph_objects_mod.Figure = FakeFigure
    graph_objects_mod.Scatter = FakeScatter
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    return FakeFigure


def _alternative_rules() -> dict:
    return {
        "base_predict": [0.72, 0.72, 0.72, 0.72],
        "base_predict_low": [0.64, 0.64, 0.64, 0.64],
        "base_predict_high": [0.80, 0.80, 0.80, 0.80],
        "classes": [1.0, 1.0, 1.0, 1.0],
        "feature": [0, 1, 2, 3],
        "feature_value": [41, 39000, "B", 0.4],
        "is_conjunctive": [False, False, False, True],
        "predict": [0.66, 0.81, 0.49, 0.77],
        "predict_low": [0.58, 0.74, 0.40, 0.72],
        "predict_high": [0.73, 0.88, 0.60, 0.83],
        "rule": ["age <= 40", None, "segment = A", "risk <= 0.5 AND tenure > 2"],
        "sampled_values": [[38, 35], [42000], ["A"], [0.1, 0.2]],
        "value": ["41", "39000", "B", "0.4"],
        "weight": [-0.06, 0.09, -0.23, 0.05],
        "weight_low": [-0.14, 0.02, -0.32, 0.00],
        "weight_high": [0.01, 0.16, -0.12, 0.11],
    }


def _dummy_alternative_explanation() -> SimpleNamespace:
    collection = SimpleNamespace(
        feature_names=["age", "income", "segment", "risk"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )

    def rank_features(*, width, num_to_show, **_kwargs):
        return sorted(range(len(width)), key=lambda index: (float(width[index]), index))[:num_to_show]

    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.72, "low": 0.64, "high": 0.80, "classes": 1.0},
        rules=_alternative_rules(),
        conjunctive_rules=None,
        has_conjunctive_rules=False,
        y_minmax=(0.0, 1.0),
        get_mode=lambda: "classification",
        is_probabilistic=lambda: True,
        is_regression=lambda: False,
        is_thresholded=lambda: False,
        is_alternative=lambda: True,
        rank_features=rank_features,
        get_rules=lambda: _alternative_rules(),
    )
    collection.explanations = [local]
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


def test_builder_enriches_hover_and_capabilities(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation(), filter_top=3))

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["base_plotspec_kind"] == "triangular"
    assert artifact["original"]["label"] == "Original Prediction"
    assert artifact["metadata"]["filter_top"] == 3
    assert artifact["metadata"]["shown_rule_count"] == 3
    assert artifact["metadata"]["missing_rule_metadata_count"] == 1
    assert artifact["interaction_capabilities"] == {
        "hover": True,
        "html_export": True,
        "filter_top": True,
        "arrows": True,
        "dropdown_filters": False,
        "click_detail_panel": False,
        "marker_uncertainty_encoding": False,
        "side_table": False,
    }
    assert all(point["hover"] for point in artifact["rule_points"])
    assert any("Rule condition unavailable" in point["hover"] for point in artifact["rule_points"])
    assert all(
        ("Rule:" in point["hover"] and (point["rule"] in point["hover"]))
        for point in artifact["rule_points"]
    )


def test_compact_rule_hover_shows_only_requested_fields(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation(), filter_top=1))
    hover_text = artifact["rule_points"][0]["hover"]

    assert "Rule:" in hover_text
    assert "Prediction:" in hover_text
    assert "Uncertainty:" in hover_text
    assert "Interval:" in hover_text
    assert "Feature:" not in hover_text
    assert "Feature index:" not in hover_text
    assert "Instance value:" not in hover_text
    assert "Alternative value:" not in hover_text
    assert "Delta prediction:" not in hover_text
    assert "Delta uncertainty:" not in hover_text
    assert "Rank:" not in hover_text


def test_renderer_returns_plotly_figure_with_points_arrows_and_reference(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=3)
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    rule_trace = next(trace for trace in result.figure.traces if trace.kwargs.get("name") == "alternatives")
    original_trace = next(trace for trace in result.figure.traces if trace.kwargs.get("name") == "original")
    reference_traces = [
        trace for trace in result.figure.traces if str(trace.kwargs.get("name", "")).startswith("triangle-reference-")
    ]
    assert result.figure is result.extras["figure"]
    assert original_trace.kwargs["x"] == [artifact["original"]["prediction"]]
    assert len(rule_trace.kwargs["x"]) == artifact["metadata"]["shown_rule_count"]
    assert len(result.figure.annotations) == artifact["metadata"]["shown_rule_count"]
    assert len(reference_traces) == 4
    assert result.figure.layout["xaxis"]["title"] == "Probability"
    assert result.figure.layout["yaxis"]["title"] == "Uncertainty"
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


def test_show_arrows_false_suppresses_arrow_annotations(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), show_arrows=False, filter_top=2)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert result.figure.annotations == []


def test_filter_top_and_max_points_limit_rule_points_and_arrows(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _dummy_alternative_explanation(),
            max_points=2,
            sort_by="delta_prediction",
        )
    )
    result = plugin.render(artifact, context=_context(_dummy_alternative_explanation(), max_points=2, sort_by="delta_prediction"))
    rule_trace = next(trace for trace in result.figure.traces if trace.kwargs.get("name") == "alternatives")

    assert artifact["metadata"]["filter_top"] == 2
    assert artifact["metadata"]["shown_rule_count"] == 2
    assert len(artifact["arrows"]) == 2
    assert len(rule_trace.kwargs["x"]) == 2
    assert len(result.figure.annotations) == 2


def test_sort_by_is_deterministic(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), sort_by="delta_prediction", filter_top=3)

    artifact_one = plugin.build(context)
    artifact_two = plugin.build(context)

    assert [point["id"] for point in artifact_one["rule_points"]] == [
        point["id"] for point in artifact_two["rule_points"]
    ]


def test_html_export_when_context_path_is_supplied(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _dummy_alternative_explanation(),
        path=str(tmp_path / "ensured_triangular_export"),
        filter_top=2,
    )
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert result.saved_paths[0].endswith("ensured_triangular_export.html")
    assert result.figure.html_paths == [result.saved_paths[0]]


def test_smoke_path_with_wrap_calibrated_explainer(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)

    features, labels = make_classification(
        n_samples=180,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_proper, x_holdout, y_proper, y_holdout = train_test_split(
        features,
        labels,
        test_size=0.4,
        random_state=0,
        stratify=labels,
    )
    x_cal, x_query, y_cal, _ = train_test_split(
        x_holdout,
        y_holdout,
        test_size=0.5,
        random_state=0,
        stratify=y_holdout,
    )

    model = LogisticRegression(random_state=0, solver="liblinear")
    explainer = WrapCalibratedExplainer(model)
    explainer.fit(x_proper, y_proper)
    explainer.calibrate(x_cal, y_cal)
    alternatives = explainer.explore_alternatives(x_query[:1])

    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(alternatives, filter_top=5, instance_index=0)
    result = plugin.render(plugin.build(context), context=context)

    assert result is not None
    assert result.artifact["artifact_type"] == STYLE_ID
    assert result.figure is result.extras["figure"]
    assert result.artifact["original"]["label"] == "Original Prediction"
    assert result.artifact["metadata"]["shown_rule_count"] >= 1
