import sys
from pathlib import Path

import pytest

pytest.importorskip("calibrated_explanations")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calibrated_explanations import CalibratedExplainer
import calibrated_explanations.plugins.registry as registry
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from ce_explanation_factual_lime import plugin as lime_plugin_mod


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


def test_plugin_should_be_runtime_consumable(monkeypatch):
    class _DummyLimePipeline:
        def __init__(self, explainer):
            self._explainer = explainer

        def explain(self, **kwargs):
            return self._explainer.explain_factual(kwargs["x_test"], _use_plugin=False)

    monkeypatch.setattr(lime_plugin_mod, "LimePipeline", _DummyLimePipeline)

    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.lime",
                "ce_explanation_factual_lime.plugin:FactualLimeExplanationPlugin",
            ]
        ),
    )
    _reset_registry_state()
    lime_plugin_mod.register_scaffold_explanation_plugin()

    descriptor = registry.find_explanation_descriptor("official.explanation.factual.lime")
    assert descriptor is not None

    x, y = make_classification(
        n_samples=80,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        x, y, test_size=0.2, random_state=0, stratify=y
    )
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        factual_plugin="official.explanation.factual.lime",
    )
    collection = explainer.explain_factual(x_test[:2])
    assert collection.explanations
    assert len(collection.explanations) == 2
    assert (
        explainer.plugin_manager.explanation_plugin_identifiers["factual"]
        == "official.explanation.factual.lime"
    )
