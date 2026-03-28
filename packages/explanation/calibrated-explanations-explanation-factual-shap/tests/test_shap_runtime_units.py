from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest

from calibrated_explanations.utils.exceptions import ConfigurationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ce_explanation_factual_shap.plugin import FactualShapExplanationPlugin
from ce_explanation_factual_shap.shap_helper import ShapHelper
from ce_explanation_factual_shap.shap_pipeline import ShapPipeline


def test_shap_helper_should_return_none_when_import_missing(monkeypatch):
    helper = ShapHelper(explainer=SimpleNamespace())
    monkeypatch.setattr(
        "ce_explanation_factual_shap.shap_helper.safe_import",
        lambda *_args, **_kwargs: None,
    )
    explainer, reference = helper.preload()
    assert explainer is None
    assert reference is None
    assert helper.enabled is False


def test_shap_helper_should_cache_explainer(monkeypatch):
    class _DummyShapModule:
        class Explainer:
            def __init__(self, _predict, _x_cal, feature_names=None):
                self.feature_names = feature_names

            def __call__(self, x, **_kwargs):
                arr = np.asarray(x)
                return {"shape": tuple(arr.shape)}

    explainer = SimpleNamespace(
        x_cal=np.array([[0.1, 0.2], [0.2, 0.3]]),
        feature_names=["f1", "f2"],
        prediction_orchestrator=SimpleNamespace(
            predict_internal=lambda x: (np.ones(len(np.asarray(x))), None, None, None)
        ),
    )
    helper = ShapHelper(explainer=explainer)
    monkeypatch.setattr(
        "ce_explanation_factual_shap.shap_helper.safe_import",
        lambda *_args, **_kwargs: _DummyShapModule,
    )

    shap_explainer, reference = helper.preload(num_test=2)
    assert shap_explainer is not None
    assert reference == {"shape": (2, 2)}
    assert helper.is_enabled() is True


def test_shap_pipeline_should_raise_when_dependency_missing(monkeypatch):
    pipeline = ShapPipeline(explainer=SimpleNamespace())
    monkeypatch.setattr(pipeline, "preload_shap", lambda num_test=None: (None, None))
    with pytest.raises(ConfigurationError, match="optional dependency is missing"):
        pipeline.explain(np.array([[1.0, 2.0]]))


def test_shap_plugin_meta_modes_and_tasks_should_match_contract():
    meta = FactualShapExplanationPlugin.plugin_meta
    assert meta["modes"] == ("factual",)
    assert meta["tasks"] == ("classification", "regression")
