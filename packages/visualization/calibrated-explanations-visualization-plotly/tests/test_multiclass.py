"""Dedicated multiclass coverage for the styles that claim multiclass support.

The support matrix (README) claims multiclass renders as a one-vs-rest view of
the predicted class, with no per-class panel. These tests make that claim
executable with a real 3-class CE workflow: every claiming style must build
and render, the rendered view must be the predicted-class one-vs-rest
probability (values in [0, 1]), and header captions must name the predicted
class per CE's P(y=<class>)/P(y!=<class>) convention.

``instance_workspace`` (dashboard) is exercised through the global explorer
payload it embeds; the Dash live path is out of scope here.
"""

from __future__ import annotations

import importlib
from types import MappingProxyType

import calibrated_explanations.plugins.registry as registry
import numpy as np
import pytest
from calibrated_explanations import CalibratedExplainer
from calibrated_explanations.plugins.plots import PlotRenderContext
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"


def _load_plugin(monkeypatch):
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap," + BOOTSTRAP_ID,
    )
    module = importlib.import_module("ce_visualization_plotly.plugin")
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()
    module.register_plotly_visualization_components()
    return module


@pytest.fixture(scope="module")
def multiclass_workflow():
    features, labels = make_classification(
        n_samples=200,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        n_classes=3,
        n_clusters_per_class=1,
        random_state=7,
    )
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=7, stratify=labels
    )
    model = RandomForestClassifier(n_estimators=25, random_state=7).fit(x_train, y_train)
    explainer = CalibratedExplainer(
        model,
        x_train,
        y_train,
        mode="classification",
        seed=7,
        class_labels=["alpha", "beta", "gamma"],
    )
    return {
        "explainer": explainer,
        "x_test": x_test,
        "y_test": y_test,
        "factual": explainer.explain_factual(x_test[:2]),
        "alternatives": explainer.explore_alternatives(x_test[:2]),
    }


def _context(explanation, style_id, intent_type, **options):
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=style_id,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _build_and_render(style_id, explanation, intent_type, **options):
    plugin = registry.find_plot_plugin(style_id)
    assert plugin is not None, style_id
    context = _context(explanation, style_id, intent_type, **options)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)
    return artifact, result


def test_factual_bars_multiclass_one_vs_rest(monkeypatch, multiclass_workflow):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.factual_bars", multiclass_workflow["factual"], "factual"
    )
    assert result.figure is not None
    bars = artifact["prediction"]["bars"]
    # One-vs-rest header: exactly the predicted class vs its complement,
    # never one panel per class.
    assert len(bars) == 2
    labels = [bar["label"] for bar in bars]
    assert any(lbl.startswith("P(y=") for lbl in labels), labels
    assert any(lbl.startswith("P(y!=") for lbl in labels), labels
    predicted = labels[0][len("P(y=") : -1]
    assert predicted in {"alpha", "beta", "gamma"}, labels
    for bar in bars:
        assert 0.0 <= bar["value"] <= 1.0


def test_factual_simple_multiclass_builds_and_renders(monkeypatch, multiclass_workflow):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.factual_simple", multiclass_workflow["factual"], "factual"
    )
    assert result.figure is not None
    assert artifact["items"], "factual_simple must produce contribution items"


def test_alternative_bars_multiclass_one_vs_rest(monkeypatch, multiclass_workflow):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.alternative_bars", multiclass_workflow["alternatives"], "alternative"
    )
    assert result.figure is not None
    # One-vs-rest: the x-axis is the predicted-class probability in [0, 1].
    # Raw calibrated interval bounds may slightly exceed [0, 1] (they are
    # clamped to the axis at render time, as in CE's matplotlib path), but the
    # calibrated point prediction itself must be a probability.
    assert artifact["axis_metadata"]["xlim"] == [0.0, 1.0]
    assert artifact["items"], "expected at least one alternative rule"
    for item in artifact["items"]:
        value = item.get("predict")
        if value is not None:
            assert 0.0 <= value <= 1.0, value


def test_alternative_feature_summary_multiclass_builds_and_renders(
    monkeypatch, multiclass_workflow
):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.alternative_feature_summary",
        multiclass_workflow["alternatives"],
        "alternative",
    )
    assert result.figure is not None


def test_ensured_multiclass_builds_and_renders(monkeypatch, multiclass_workflow):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.ensured", multiclass_workflow["alternatives"], "alternative"
    )
    assert result.figure is not None


def test_uncertainty_quadrant_multiclass_builds_and_renders(monkeypatch, multiclass_workflow):
    _load_plugin(monkeypatch)
    artifact, result = _build_and_render(
        "plotly.local.uncertainty_quadrant", multiclass_workflow["factual"], "factual"
    )
    assert result.figure is not None
    assert artifact["items"], "quadrant must extract weighted rules"


def test_instance_explorer_multiclass_builds_and_renders(monkeypatch, multiclass_workflow):
    module = _load_plugin(monkeypatch)
    module  # noqa: B018 — registration side of the fixture
    explainer = multiclass_workflow["explainer"]
    x_test = multiclass_workflow["x_test"]
    y_test = multiclass_workflow["y_test"]

    from ce_visualization_plotly.instance_explorer import GlobalInstanceExplorerPlotBuilder

    proba, (low, high) = explainer.predict_proba(x_test, uq_interval=True)
    payload = {
        "proba": proba,
        "predict": None,
        "low": low,
        "high": high,
        "uncertainty": np.array(high) - np.array(low),
        "y": list(y_test),
        "is_regularized": True,
        "threshold": None,
        "class_labels": ["alpha", "beta", "gamma"],
        "x": x_test,
    }
    context = PlotRenderContext(
        explanation=None,
        instance_metadata=MappingProxyType({"type": "global"}),
        style="plotly.global.instance_explorer",
        intent=MappingProxyType({"type": "global"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"payload": payload, "include_instance_records": True}),
    )
    artifact = GlobalInstanceExplorerPlotBuilder().build(context)
    assert artifact.get("instance_records"), "explorer must produce instance records"
