from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from types import MappingProxyType

import calibrated_explanations.plugins.registry as registry
import numpy as np
import pytest
from calibrated_explanations.plugins.plots import PlotRenderContext
from calibrated_explanations import CalibratedExplainer
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


STYLE_ID = "official.visualization.factual.shap"
BUILDER_ID = "official.visualization.factual.shap.builder"
RENDERER_ID = "official.visualization.factual.shap.renderer"


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


def _dummy_collection() -> SimpleNamespace:
    return SimpleNamespace(
        batch_metadata={
            "shap": {
                "feature_names": ["a", "b", "c"],
                "data": [[1.0, 2.0, 3.0], [1.5, 2.5, 3.5]],
                "values": {
                    "center": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                    "lower": [[0.05, 0.1, 0.15], [0.2, 0.25, 0.3]],
                    "upper": [[0.15, 0.3, 0.45], [0.6, 0.75, 0.9]],
                    "uncertainty": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                },
                "base_values": {
                    "center": [0.2, 0.2],
                    "lower": [0.1, 0.1],
                    "upper": [0.3, 0.3],
                    "uncertainty": [0.2, 0.2],
                },
                "_runtime": {
                    "explanations": {}
                },
            }
        },
        explanations=[],
    )


def test_adapter_should_reconstruct_shap_explanation_from_metadata():
    pytest.importorskip("shap")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    adapter_mod = importlib.import_module("ce_visualization_factual_shap.adapter")

    collection = _dummy_collection()
    explanation = adapter_mod.to_shap_explanation(collection, bound="uncertainty")
    assert explanation.values.shape == (2, 3)
    assert explanation.base_values.shape == (2,)
    assert explanation.feature_names == ["a", "b", "c"]

    row = adapter_mod.to_shap_explanation(collection, bound="center", instance_index=0)
    assert np.asarray(row.values, dtype=float) == pytest.approx([0.1, 0.2, 0.3])


def test_adapter_should_create_fresh_figure_for_each_render(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    adapter_mod = importlib.import_module("ce_visualization_factual_shap.adapter")

    class _DummyFigure:
        def __init__(self, figure_id: int) -> None:
            self.figure_id = figure_id

    class _DummyPyplot:
        def __init__(self) -> None:
            self._next_id = 0

        def figure(self):
            self._next_id += 1
            return _DummyFigure(self._next_id)

    class _DummyShapPlots:
        @staticmethod
        def waterfall(explanation, show=True, **kwargs):
            _ = show
            _ = kwargs
            _ = explanation

    class _DummyExplanation:
        def __init__(self, *, values, base_values, data, feature_names):
            self.values = values
            self.base_values = base_values
            self.data = data
            self.feature_names = feature_names

        def __getitem__(self, index):
            return _DummyExplanation(
                values=self.values[index],
                base_values=self.base_values[index],
                data=self.data[index],
                feature_names=self.feature_names,
            )

    class _DummyShap:
        Explanation = _DummyExplanation
        plots = _DummyShapPlots()

    pyplot = _DummyPyplot()
    monkeypatch.setattr(adapter_mod, "_import_pyplot", lambda: pyplot)
    monkeypatch.setattr(adapter_mod, "_import_shap", lambda: _DummyShap)

    first = adapter_mod.plot_shap(
        _dummy_collection(),
        kind="waterfall",
        bound="center",
        instance_index=0,
        prefer_runtime=False,
        show=False,
    )
    second = adapter_mod.plot_shap(
        _dummy_collection(),
        kind="waterfall",
        bound="center",
        instance_index=0,
        prefer_runtime=False,
        show=False,
    )

    assert first is not second
    assert first.figure_id == 1
    assert second.figure_id == 2


def test_visualization_plugin_should_register_style_and_render(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    plugin_mod = importlib.import_module("ce_visualization_factual_shap.plugin")

    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "ce_visualization_factual_shap.plugin:FactualShapVisualizationBootstrap",
                STYLE_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    _reset_registry_state()
    plugin_mod.register_factual_shap_visualization_components()

    builder_descriptor = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_descriptor = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    assert builder_descriptor is not None
    assert renderer_descriptor is not None
    assert style_descriptor is not None

    sentinel_figure = object()

    def _fake_plot_shap(explanation, *, kind, bound, instance_index, prefer_runtime, show, **kwargs):
        _ = explanation
        _ = show
        assert kind == "waterfall"
        assert bound == "center"
        assert instance_index == 0
        assert prefer_runtime is True
        assert kwargs["max_display"] == 5
        return sentinel_figure

    monkeypatch.setattr(plugin_mod, "plot_shap", _fake_plot_shap)

    collection = _dummy_collection()
    context = PlotRenderContext(
        explanation=collection,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "shap_kind": "waterfall",
                "shap_bound": "center",
                "instance_index": 0,
                "prefer_runtime": True,
                "max_display": 5,
            }
        ),
    )

    plugin = registry.find_plot_plugin(STYLE_ID)
    assert plugin is not None
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)
    assert result.figure is sentinel_figure
    assert result.extras["shap_kind"] == "waterfall"


def test_collection_plot_should_return_plugin_result_for_custom_style(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "explanation" / "calibrated-explanations-explanation-factual-shap" / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    shap_plugin_mod = importlib.import_module("ce_explanation_factual_shap.plugin")
    viz_plugin_mod = importlib.import_module("ce_visualization_factual_shap.plugin")

    class _DummyShapPipeline:
        def __init__(self, _explainer):
            pass

        def explain_bounds(self, x_test, *, bins=None, shap_kwargs=None):
            _ = bins
            _ = shap_kwargs
            n_rows, n_features = x_test.shape
            row = [0.1 * (feature + 1) for feature in range(n_features)]
            return {
                "center": {
                    "values": [row for _ in range(n_rows)],
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": "center-runtime",
                },
                "lower": {
                    "values": [row for _ in range(n_rows)],
                    "base_values": [0.1 for _ in range(n_rows)],
                    "raw": "lower-runtime",
                },
                "upper": {
                    "values": [row for _ in range(n_rows)],
                    "base_values": [0.3 for _ in range(n_rows)],
                    "raw": "upper-runtime",
                },
                "uncertainty": {
                    "values": [row for _ in range(n_rows)],
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": "uncertainty-runtime",
                },
            }

    sentinel_figure = object()

    def _fake_plot_shap(explanation, *, kind, bound, instance_index, prefer_runtime, show, **kwargs):
        _ = explanation
        _ = show
        assert kind == "waterfall"
        assert bound == "center"
        assert instance_index == 0
        assert prefer_runtime is True
        assert kwargs["max_display"] == 6
        assert "style" not in kwargs
        assert "rnk_metric" not in kwargs
        return sentinel_figure

    monkeypatch.setattr(shap_plugin_mod, "ShapPipeline", _DummyShapPipeline)
    monkeypatch.setattr(viz_plugin_mod, "plot_shap", _fake_plot_shap)
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.shap",
                "ce_explanation_factual_shap.plugin:FactualShapExplanationPlugin",
                "ce_visualization_factual_shap.plugin:FactualShapVisualizationBootstrap",
                STYLE_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    _reset_registry_state()
    shap_plugin_mod.register_scaffold_explanation_plugin()
    viz_plugin_mod.register_factual_shap_visualization_components()

    features, labels = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        features, labels, test_size=0.2, random_state=0, stratify=labels
    )
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        factual_plugin="official.explanation.factual.shap",
    )
    explanations = explainer.explain_factual(x_test[:1])

    result = explanations.plot(
        style=STYLE_ID,
        show=False,
        shap_kind="waterfall",
        shap_bound="center",
        instance_index=0,
        max_display=6,
    )

    assert result is not None
    assert result.figure is sentinel_figure
    assert result.extras["shap_kind"] == "waterfall"


def test_collection_plot_should_treat_instance_index_as_selector_for_custom_style(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "explanation" / "calibrated-explanations-explanation-factual-shap" / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    shap_plugin_mod = importlib.import_module("ce_explanation_factual_shap.plugin")
    viz_plugin_mod = importlib.import_module("ce_visualization_factual_shap.plugin")

    class _DummyShapPipeline:
        def __init__(self, _explainer):
            pass

        def explain_bounds(self, x_test, *, bins=None, shap_kwargs=None):
            _ = bins
            _ = shap_kwargs
            n_rows, n_features = x_test.shape
            rows = [
                [float(row + feature + 1) for feature in range(n_features)]
                for row in range(n_rows)
            ]
            return {
                "center": {
                    "values": rows,
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": None,
                },
                "lower": {
                    "values": rows,
                    "base_values": [0.1 for _ in range(n_rows)],
                    "raw": None,
                },
                "upper": {
                    "values": rows,
                    "base_values": [0.3 for _ in range(n_rows)],
                    "raw": None,
                },
                "uncertainty": {
                    "values": rows,
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": None,
                },
            }

    sentinel_figure = object()

    def _fake_plot_shap(explanation, *, kind, bound, instance_index, prefer_runtime, show, **kwargs):
        _ = explanation
        _ = show
        _ = kwargs
        assert kind == "waterfall"
        assert bound == "center"
        assert instance_index == 1
        assert prefer_runtime is True
        return sentinel_figure

    monkeypatch.setattr(shap_plugin_mod, "ShapPipeline", _DummyShapPipeline)
    monkeypatch.setattr(viz_plugin_mod, "plot_shap", _fake_plot_shap)
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.shap",
                "ce_explanation_factual_shap.plugin:FactualShapExplanationPlugin",
                "ce_visualization_factual_shap.plugin:FactualShapVisualizationBootstrap",
                STYLE_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    _reset_registry_state()
    shap_plugin_mod.register_scaffold_explanation_plugin()
    viz_plugin_mod.register_factual_shap_visualization_components()

    features, labels = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        features, labels, test_size=0.2, random_state=0, stratify=labels
    )
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        factual_plugin="official.explanation.factual.shap",
    )
    explanations = explainer.explain_factual(x_test[:2])

    result = explanations.plot(
        style=STYLE_ID,
        show=False,
        shap_kind="waterfall",
        shap_bound="center",
        instance_index=1,
        max_display=6,
    )

    assert result is not None
    assert not isinstance(result, list)
    assert result.figure is sentinel_figure


def test_collection_beeswarm_should_return_single_plot_result(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "explanation" / "calibrated-explanations-explanation-factual-shap" / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    shap_plugin_mod = importlib.import_module("ce_explanation_factual_shap.plugin")
    viz_plugin_mod = importlib.import_module("ce_visualization_factual_shap.plugin")

    class _DummyShapPipeline:
        def __init__(self, _explainer):
            pass

        def explain_bounds(self, x_test, *, bins=None, shap_kwargs=None):
            _ = bins
            _ = shap_kwargs
            n_rows, n_features = x_test.shape
            rows = [
                [float((row + 1) * (feature + 1)) for feature in range(n_features)]
                for row in range(n_rows)
            ]
            return {
                "center": {
                    "values": rows,
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": "center-runtime",
                },
                "lower": {
                    "values": rows,
                    "base_values": [0.1 for _ in range(n_rows)],
                    "raw": "lower-runtime",
                },
                "upper": {
                    "values": rows,
                    "base_values": [0.3 for _ in range(n_rows)],
                    "raw": "upper-runtime",
                },
                "uncertainty": {
                    "values": rows,
                    "base_values": [0.2 for _ in range(n_rows)],
                    "raw": "uncertainty-runtime",
                },
            }

    sentinel_figure = object()

    def _fake_plot_shap(explanation, *, kind, bound, instance_index, prefer_runtime, show, **kwargs):
        _ = show
        assert kind == "beeswarm"
        assert bound == "center"
        assert instance_index is None
        assert prefer_runtime is True
        assert kwargs["max_display"] == 6
        assert hasattr(explanation, "batch_metadata")
        assert hasattr(explanation, "explanations")
        return sentinel_figure

    monkeypatch.setattr(shap_plugin_mod, "ShapPipeline", _DummyShapPipeline)
    monkeypatch.setattr(viz_plugin_mod, "plot_shap", _fake_plot_shap)
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.shap",
                "ce_explanation_factual_shap.plugin:FactualShapExplanationPlugin",
                "ce_visualization_factual_shap.plugin:FactualShapVisualizationBootstrap",
                STYLE_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    _reset_registry_state()
    shap_plugin_mod.register_scaffold_explanation_plugin()
    viz_plugin_mod.register_factual_shap_visualization_components()

    features, labels = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        features, labels, test_size=0.2, random_state=0, stratify=labels
    )
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        factual_plugin="official.explanation.factual.shap",
    )
    explanations = explainer.explain_factual(x_test[:2])

    result = explanations.plot(
        style=STYLE_ID,
        show=False,
        shap_kind="beeswarm",
        shap_bound="center",
        max_display=6,
    )

    assert result is not None
    assert not isinstance(result, list)
    assert result.figure is sentinel_figure
