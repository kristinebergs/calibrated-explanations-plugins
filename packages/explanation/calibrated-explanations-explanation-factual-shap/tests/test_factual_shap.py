"""Behavior tests for the factual SHAP explanation plugin."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations import CalibratedExplainer
from calibrated_explanations.plugins.explanations import ExplanationRequest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


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


def test_should_emit_feature_names_with_lower_upper_shap_weights(monkeypatch):
    """Ensure the plugin emits feature-name labels and SHAP lower/upper weights."""

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    shap_plugin_mod = importlib.import_module("ce_explanation_factual_shap.plugin")

    class _DummyShapPipeline:
        def __init__(self, _explainer):
            pass

        def explain_bounds(self, x_test, *, bins=None, shap_kwargs=None):
            """Return deterministic center/lower/upper/uncertainty attribution matrices."""

            _ = bins
            _ = shap_kwargs
            n_rows, n_features = x_test.shape
            center = []
            lower = []
            upper = []
            for row in range(n_rows):
                center.append([(row + 1.0) + feature / 10.0 for feature in range(n_features)])
                lower.append([(row + 0.5) + feature / 10.0 for feature in range(n_features)])
                upper.append([(row + 1.5) + feature / 10.0 for feature in range(n_features)])
            return {
                "center": center,
                "lower": lower,
                "upper": upper,
                "uncertainty": [
                    [upper_value - lower_value for upper_value, lower_value in zip(upper_row, lower_row, strict=False)]
                    for upper_row, lower_row in zip(upper, lower, strict=False)
                ],
            }

    monkeypatch.setattr(shap_plugin_mod, "ShapPipeline", _DummyShapPipeline)

    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.shap",
                "ce_explanation_factual_shap.plugin:FactualShapExplanationPlugin",
            ]
        ),
    )
    _reset_registry_state()
    shap_plugin_mod.register_scaffold_explanation_plugin()

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

    collection = explainer.explain_factual(x_test[:2])

    assert collection.explanations
    first = collection.explanations[0]
    rules = first.get_rules()

    for label in rules["rule"]:
        assert "<" not in label
        assert ">" not in label
        assert "=" not in label

    feature_names = list(explainer.feature_names)
    for label in rules["rule"]:
        assert label in feature_names

    for feature_index, center_weight, lower_weight, upper_weight in zip(
        rules["feature"],
        rules["weight"],
        rules["weight_low"],
        rules["weight_high"],
        strict=False,
    ):
        assert center_weight == pytest.approx(1.0 + feature_index / 10.0)
        assert lower_weight == pytest.approx(0.5 + feature_index / 10.0)
        assert upper_weight == pytest.approx(1.5 + feature_index / 10.0)

    shap_meta = collection.batch_metadata["shap"]
    uq_meta = shap_meta["uncertainty_attributions"]
    assert uq_meta["enabled"] is True
    assert uq_meta["target"] == "interval_width"
    assert uq_meta["formula"] == "upper - lower"
    assert uq_meta["feature_names"] == feature_names
    assert isinstance(uq_meta["values"], list)
    assert len(uq_meta["values"]) == 2
    for row in uq_meta["values"]:
        assert isinstance(row, list)
        assert len(row) == len(feature_names)
    for feature_index, value in enumerate(uq_meta["values"][0]):
        assert value == pytest.approx(1.0)


def test_should_use_factual_scaffold_and_reconstruct_predict_bounds_when_explain_batch_called(monkeypatch):
    """Verify explain_batch uses factual scaffold and SHAP lower/upper weights."""

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    shap_plugin_mod = importlib.import_module("ce_explanation_factual_shap.plugin")

    class _DummyShapPipeline:
        def __init__(self, _explainer):
            pass

        def explain_bounds(self, x_test, *, bins=None, shap_kwargs=None):
            _ = bins
            _ = shap_kwargs
            n_rows, n_features = x_test.shape
            return {
                "center": [[0.1 * (feature + 1) for feature in range(n_features)] for _ in range(n_rows)],
                "lower": [[0.05 * (feature + 1) for feature in range(n_features)] for _ in range(n_rows)],
                "upper": [[0.15 * (feature + 1) for feature in range(n_features)] for _ in range(n_rows)],
                "uncertainty": [[0.10 * (feature + 1) for feature in range(n_features)] for _ in range(n_rows)],
            }

    monkeypatch.setattr(shap_plugin_mod, "ShapPipeline", _DummyShapPipeline)

    class _DummyExplanation:
        def __init__(self) -> None:
            self.rules = {
                "feature": [0, 1, 2],
                "rule": ["f0 <= 1.0", "f1 <= 2.0", "f2 <= 3.0"],
                "weight": [0.0, 0.0, 0.0],
                "weight_low": [0.0, 0.0, 0.0],
                "weight_high": [0.0, 0.0, 0.0],
                "base_predict": [0.2],
                "base_predict_low": [0.1],
                "base_predict_high": [0.3],
                "predict": [0.0, 0.0, 0.0],
                "predict_low": [0.0, 0.0, 0.0],
                "predict_high": [0.0, 0.0, 0.0],
            }

        def get_rules(self):
            return self.rules

    dummy_explanation = _DummyExplanation()
    dummy_collection = SimpleNamespace(
        explanations=[dummy_explanation],
        mode="factual",
        calibrated_explainer=SimpleNamespace(),
        x_test=[[0.0, 1.0, 2.0]],
        y_threshold=None,
        bins=None,
        features_to_ignore=(),
        low_high_percentiles=(5, 95),
        feature_filter_per_instance_ignore=None,
        filter_telemetry=None,
    )

    class _DummyExplainer:
        feature_names = ["a", "b", "c"]

        def explain_factual(self, *_args, **_kwargs):
            return dummy_collection

        def explain_fast(self, *_args, **_kwargs):  # pragma: no cover - must not be called
            raise AssertionError("Plugin must not depend on explain_fast")

    class _DummyPredictBridge:
        def predict(self, *_args, **_kwargs):
            return {"predict": [0.2], "low": [0.1], "high": [0.3]}

    plugin = shap_plugin_mod.FactualShapExplanationPlugin()
    context = SimpleNamespace(
        task="classification",
        feature_names=["a", "b", "c"],
        helper_handles={"explainer": _DummyExplainer()},
        predict_bridge=_DummyPredictBridge(),
    )
    plugin.initialize(context)

    request = ExplanationRequest(
        threshold=None,
        low_high_percentiles=(5, 95),
        bins=None,
        features_to_ignore=(),
        extras={},
    )
    x_test = np.asarray([[1.0, 2.0, 3.0]], dtype=float)
    batch = plugin.explain_batch(x_test, request)

    assert batch.collection_metadata["shap"]["lower_upper_attributions"] is True
    uq_meta = batch.collection_metadata["shap"]["uncertainty_attributions"]
    assert uq_meta["enabled"] is True
    assert uq_meta["target"] == "interval_width"
    assert uq_meta["formula"] == "upper - lower"
    assert uq_meta["feature_names"] == ["a", "b", "c"]
    assert uq_meta["values"][0] == pytest.approx([0.1, 0.2, 0.3])

    rules = dummy_explanation.rules
    assert rules["rule"] == ["a", "b", "c"]
    assert all("<" not in label and ">" not in label and "=" not in label for label in rules["rule"])

    for index in range(len(rules["feature"])):
        assert rules["predict"][index] == pytest.approx(rules["base_predict"][0] + rules["weight"][index])
        assert rules["predict_low"][index] == pytest.approx(
            rules["base_predict_low"][0] + rules["weight_low"][index]
        )
        assert rules["predict_high"][index] == pytest.approx(
            rules["base_predict_high"][0] + rules["weight_high"][index]
        )
