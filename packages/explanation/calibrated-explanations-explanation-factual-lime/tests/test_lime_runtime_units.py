from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest

from calibrated_explanations.utils.exceptions import (
    ConfigurationError,
    DataShapeError,
    ValidationError,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ce_explanation_factual_lime.lime_helper import LimeHelper
from ce_explanation_factual_lime.lime_pipeline import LimePipeline
from ce_explanation_factual_lime.plugin import FactualLimeExplanationPlugin


class _DummyCollection:
    def __init__(self, _explainer, x_test, threshold, bins, condition_source=None):
        self.x_test = np.asarray(x_test)
        self.threshold = threshold
        self.bins = bins
        self.condition_source = condition_source
        self.low_high_percentiles = None
        self.finalized = None

    def finalize_fast(
        self, feature_weights, feature_predict, prediction, instance_time=None, total_time=None
    ):
        self.finalized = {
            "feature_weights": feature_weights,
            "feature_predict": feature_predict,
            "prediction": prediction,
            "instance_time": instance_time,
            "total_time": total_time,
        }


class _DummyLimeExplanation:
    def __init__(self, value0=0.1, value1=0.2, proba=0.7):
        self.local_exp = {1: [(0, value0), (1, value1)]}
        self.predict_proba = [1.0 - proba, proba]


class _DummyLimeExplainer:
    def explain_instance(self, _instance, predict_fn=None, num_features=None):
        assert predict_fn is not None
        assert num_features is not None
        return _DummyLimeExplanation()


def _make_lime_explainer(*, mode="classification", multiclass=False, mondrian=False):
    classes = np.array([1, 0], dtype=int) if multiclass else np.array([1, 1], dtype=int)
    explainer = SimpleNamespace(
        num_features=2,
        mode=mode,
        condition_source="prediction",
        prediction_orchestrator=SimpleNamespace(
            predict_internal=lambda x, **_kwargs: (
                np.full(len(np.asarray(x)), 0.6, dtype=float),
                np.full(len(np.asarray(x)), 0.4, dtype=float),
                np.full(len(np.asarray(x)), 0.8, dtype=float),
                classes,
            )
        ),
        latest_explanation=None,
    )
    explainer.is_mondrian = lambda: mondrian
    explainer.is_multiclass = lambda: multiclass
    return explainer


def test_lime_helper_should_return_none_when_import_missing(monkeypatch):
    helper = LimeHelper(explainer=SimpleNamespace())
    monkeypatch.setattr(
        "ce_explanation_factual_lime.lime_helper.safe_import",
        lambda *_args, **_kwargs: None,
    )
    explainer, reference = helper.preload()
    assert explainer is None
    assert reference is None


def test_lime_pipeline_should_raise_for_shape_and_mondrian(monkeypatch):
    import ce_explanation_factual_lime.lime_pipeline as lime_pipeline_mod

    monkeypatch.setattr(lime_pipeline_mod, "CalibratedExplanations", _DummyCollection)

    shape_explainer = _make_lime_explainer()
    shape_pipeline = LimePipeline(shape_explainer)
    monkeypatch.setattr(shape_pipeline, "_preload_lime", lambda: (_DummyLimeExplainer(), None))
    with pytest.raises(DataShapeError, match="number of features"):
        shape_pipeline.explain(np.array([[1.0, 2.0, 3.0]]))

    mondrian_explainer = _make_lime_explainer(mondrian=True)
    mondrian_pipeline = LimePipeline(mondrian_explainer)
    monkeypatch.setattr(
        mondrian_pipeline, "_preload_lime", lambda: (_DummyLimeExplainer(), None)
    )
    with pytest.raises(ValidationError, match="bins parameter must be specified"):
        mondrian_pipeline.explain(np.array([[1.0, 2.0]]), bins=None)


def test_lime_pipeline_should_raise_when_dependency_missing(monkeypatch):
    import ce_explanation_factual_lime.lime_pipeline as lime_pipeline_mod

    monkeypatch.setattr(lime_pipeline_mod, "CalibratedExplanations", _DummyCollection)
    pipeline = LimePipeline(_make_lime_explainer())
    monkeypatch.setattr(pipeline, "_preload_lime", lambda: (None, None))
    with pytest.raises(ConfigurationError, match="optional dependency is missing"):
        pipeline.explain(np.array([[1.0, 2.0]]))


def test_lime_pipeline_should_generate_collection(monkeypatch):
    import ce_explanation_factual_lime.lime_pipeline as lime_pipeline_mod

    monkeypatch.setattr(lime_pipeline_mod, "CalibratedExplanations", _DummyCollection)
    monkeypatch.setattr(lime_pipeline_mod, "assert_threshold", lambda threshold, x: None)

    pipeline = LimePipeline(_make_lime_explainer(mode="regression"))
    monkeypatch.setattr(pipeline, "_preload_lime", lambda: (_DummyLimeExplainer(), None))
    out = pipeline.explain(np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert isinstance(out, _DummyCollection)
    assert out.finalized is not None


def test_lime_plugin_meta_modes_and_tasks_should_match_contract():
    meta = FactualLimeExplanationPlugin.plugin_meta
    assert meta["modes"] == ("factual",)
    assert meta["tasks"] == ("classification", "regression")
