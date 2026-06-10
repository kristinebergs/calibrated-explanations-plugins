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

STYLE_ID = "plotly.local.uncertainty_quadrant"
BUILDER_ID = "official.visualization.plotly.local.uncertainty_quadrant.builder"
RENDERER_ID = "official.visualization.plotly.local.uncertainty_quadrant.renderer"
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


def _context(explanation, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
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
            self.vlines = []
            self.hlines = []
            self.annotations = []
            self.layout = {}
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace):
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_hline(self, **kwargs):
            self.hlines.append(kwargs)

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


def _dummy_explanation(rules: dict) -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income", "score", "risk", "margin"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.7, "low": 0.6, "high": 0.8, "classes": 1},
        rules=rules,
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


def _quadrant_rules() -> dict:
    return {
        "weight": [2.0, -1.5, 0.2, 0.1, 0.4],
        "weight_low": [1.8, -2.3, 0.1, 0.05, -0.2],
        "weight_high": [2.3, -1.1, 0.3, 0.85, 0.7],
        "rule": [
            "age > 30",
            "income <= 40",
            "score > 0",
            "risk <= 1",
            "margin > 0",
        ],
        "feature": [0, 1, 2, 3, 4],
        "value": ["31", "39", "0.2", "0.7", "0.1"],
        "feature_value": [31, 39, 0.2, 0.7, 0.1],
    }


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


def test_artifact_uses_absolute_impact_width_and_zero_crossing(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _dummy_explanation(_quadrant_rules()),
            impact_threshold=1.0,
            uncertainty_threshold=0.6,
            threshold_strategy="explicit",
            sort_by="input",
        )
    )

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["thresholds"]["impact"] == pytest.approx(1.0)
    assert artifact["thresholds"]["uncertainty"] == pytest.approx(0.6)
    assert artifact["items"][1]["contribution"] == pytest.approx(-1.5)
    assert artifact["items"][1]["absolute_impact"] == pytest.approx(1.5)
    assert artifact["items"][1]["interval_width"] == pytest.approx(1.2)
    assert artifact["items"][4]["crosses_zero"] is True
    assert artifact["items"][4]["direction"] == "crosses_zero"
    assert artifact["items"][4]["status_flags"] == ("sign_uncertain",)


def test_quadrant_assignment_for_all_four_quadrants(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _dummy_explanation(_quadrant_rules()),
            impact_threshold=1.0,
            uncertainty_threshold=0.6,
            threshold_strategy="explicit",
            sort_by="input",
        )
    )

    quadrants = {item["rule"]: item["quadrant"] for item in artifact["items"]}
    assert quadrants["age > 30"] == "robust_driver"
    assert quadrants["income <= 40"] == "uncertain_driver"
    assert quadrants["score > 0"] == "stable_minor"
    assert quadrants["risk <= 1"] == "weak_or_noisy"
    assert quadrants["margin > 0"] == "weak_or_noisy"


def test_filter_top_and_sort_by_absolute_impact(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _dummy_explanation(_quadrant_rules()),
            filter_top=2,
            sort_by="absolute_impact",
        )
    )

    assert [item["rule"] for item in artifact["items"]] == ["age > 30", "income <= 40"]


def test_degenerate_thresholds_use_deterministic_fallback(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "weight": [0.0, 0.0, 0.0],
        "weight_low": [0.0, 0.0, 0.0],
        "weight_high": [0.0, 0.0, 0.0],
        "rule": ["a", "b", "c"],
        "feature": [0, 1, 2],
        "value": [0, 0, 0],
        "feature_value": [0, 0, 0],
    }

    artifact = plugin.build(
        _context(_dummy_explanation(rules), threshold_strategy="median", sort_by="input")
    )

    assert artifact["thresholds"]["impact"] == 0.0
    assert artifact["thresholds"]["uncertainty"] == 0.0
    assert artifact["thresholds"]["impact_source"] == "median:degenerate"
    assert artifact["thresholds"]["uncertainty_source"] == "median:degenerate"
    assert all(item["crosses_zero"] for item in artifact["items"])


def test_renderer_returns_plotly_figure_with_absolute_x_values(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _dummy_explanation(_quadrant_rules()),
        impact_threshold=1.0,
        uncertainty_threshold=0.6,
        threshold_strategy="explicit",
        sort_by="input",
    )
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    trace_kwargs = result.figure.traces[0].kwargs
    assert result.figure is result.extras["figure"]
    assert trace_kwargs["x"] == [item["absolute_impact"] for item in artifact["items"]]
    assert trace_kwargs["x"][1] == pytest.approx(1.5)
    assert result.figure.vlines[0]["x"] == pytest.approx(1.0)
    assert result.figure.hlines[0]["y"] == pytest.approx(0.6)
    assert len(result.figure.annotations) == 4
    assert result.figure.layout["xaxis_title"] == "Absolute local impact"
    assert result.figure.layout["yaxis_title"] == "Calibrated uncertainty width"
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


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
        features, labels, test_size=0.2, random_state=0, stratify=labels
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

    assert result is not None
    assert result.artifact["artifact_type"] == STYLE_ID
    assert len(result.artifact["items"]) == len(explanations.explanations[0].rules["weight"])
    assert result.figure is result.extras["figure"]


def test_factual_regression_smoke_with_calibrated_explainer(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)

    features, target = make_regression(n_samples=120, n_features=4, noise=0.2, random_state=1)
    x_train, x_test, y_train, _ = train_test_split(features, target, test_size=0.2, random_state=0)
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

    assert result is not None
    assert result.artifact["task"] == "regression"
    assert len(result.artifact["items"]) == 3
