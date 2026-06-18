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
        def __init__(self):
            self.traces = []
            self.vlines = []
            self.layout = {}
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace):
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def write_html(self, path):
            self.html_paths.append(path)
            Path(path).write_text("<html></html>", encoding="utf-8")

        def show(self):
            self.shown = True

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    graph_objects_mod.Bar = FakeBar
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Figure = FakeFigure
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
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


def test_renderer_default_has_bar_trace_no_interval_trace_and_zero_line(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_explanation(), sort_by="original")
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    assert len(result.figure.traces) == 1
    assert result.figure.traces[0].__class__.__name__ == "FakeBar"
    assert result.figure.vlines[0]["x"] == 0
    assert result.figure is result.extras["figure"]
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


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
    context = _context(_dummy_explanation(), show_uncertainty=True)
    result = plugin.render(plugin.build(context), context=context)

    assert len(result.figure.traces) == 2
    assert result.figure.traces[1].__class__.__name__ == "FakeScatter"
    assert result.figure.traces[1].kwargs["name"] == "contribution interval"


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
