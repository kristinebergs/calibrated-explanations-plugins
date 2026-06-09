import pytest

pytest.importorskip("calibrated_explanations")

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import CalibratedExplainer
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


def test_plugin_should_be_runtime_consumable(monkeypatch):
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.alternative.example",
                "ce_explanation_alternative_example.plugin:AlternativeExampleExplanationPlugin",
            ]
        ),
    )
    _reset_registry_state()
    registry.load_entrypoint_plugins(include_untrusted=False)

    descriptor = registry.find_explanation_descriptor("official.explanation.alternative.example")
    assert descriptor is not None
    assert descriptor.trusted is True

    x, y = make_classification(
        n_samples=80,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=0, stratify=y)
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        alternative_plugin="official.explanation.alternative.example",
    )
    collection = explainer.explore_alternatives(x_test[:2])
    assert collection.explanations
    assert len(collection.explanations) == 2
    assert (
        explainer.plugin_manager.explanation_plugin_identifiers["alternative"]
        == "official.explanation.alternative.example"
    )
