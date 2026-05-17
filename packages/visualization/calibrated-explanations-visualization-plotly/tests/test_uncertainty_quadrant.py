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
BUILDER_ID = "plotly.local.uncertainty_quadrant.builder"
RENDERER_ID = "plotly.local.uncertainty_quadrant.renderer"


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
    module = importlib.import_module("ce_visualization_plotly.plugin")
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
                STYLE_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
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
            self.layout = {}
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace):
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_hline(self, **kwargs):
            self.hlines.append(kwargs)

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


def _dummy_explanation():
    collection = SimpleNamespace(feature_names=["age", "income", "score"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.7, "low": 0.6, "high": 0.8, "classes": 1},
        rules={
            "weight": [2.0, 0.1, -1.0],
            "weight_low": [1.8, -0.2, -1.2],
            "weight_high": [2.3, 0.3, -0.8],
            "rule": ["age > 30", "income <= 40", "score > 0"],
            "feature": [0, 1, 2],
            "value": ["31", "39", "0.2"],
            "feature_value": [31, 39, 0.2],
        },
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


def test_registration_and_trust_resolution(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    assert registry.find_plot_builder_descriptor(BUILDER_ID) is not None
    assert registry.find_plot_renderer_descriptor(RENDERER_ID) is not None
    assert registry.find_plot_style_descriptor(STYLE_ID) is not None
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


def test_artifact_thresholds_widths_and_zero_crossing_status(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), sort_by="input"))

    assert artifact["artifact_type"] == STYLE_ID
    assert len(artifact["items"]) == 3
    assert artifact["thresholds"]["effect"] == pytest.approx(1.0)
    assert artifact["thresholds"]["width"] == pytest.approx(0.5)
    assert artifact["items"][0]["interval_width"] == pytest.approx(0.5)
    assert artifact["items"][1]["status_label"] == "sign_uncertain"
    assert artifact["items"][2]["status_label"] == "robust_driver"


def test_filter_top_and_sort_by(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_explanation(), filter_top=2, sort_by="width"))

    assert [item["rule_label"] for item in artifact["items"]] == ["income <= 40", "age > 30"]


def test_renderer_returns_plotly_figure_without_fallback_warnings(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="input")
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    assert result.figure is result.extras["figure"]
    assert len(result.figure.traces) == 1
    assert result.figure.vlines[0]["x"] == 0
    assert result.figure.hlines[0]["y"] == pytest.approx(artifact["thresholds"]["width"])
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
    x_train, x_test, y_train, _ = train_test_split(
        features, target, test_size=0.2, random_state=0
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

    assert result is not None
    assert result.artifact["metadata"]["task"] == "regression"
    assert len(result.artifact["items"]) == 3
