import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

pytest.importorskip("calibrated_explanations")

from calibrated_explanations import CalibratedExplainer
import calibrated_explanations.plugins.registry as registry
from ce_explanation_factual_example import FactualExampleExplanationPlugin


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


def test_explanation_plugin_should_be_discoverable_and_runtime_valid(monkeypatch):
    plugin_id = FactualExampleExplanationPlugin.plugin_meta["name"]
    trust_ids = [plugin_id, "ce_explanation_factual_example.plugin:FactualExampleExplanationPlugin"]
    monkeypatch.setenv("CE_TRUST_PLUGIN", ",".join(trust_ids))
    _reset_registry_state()
    registry.load_entrypoint_plugins(include_untrusted=False)

    descriptor = registry.find_explanation_descriptor(plugin_id)
    assert descriptor is not None
    assert descriptor.trusted is True

    x, y = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(
        x, y, test_size=0.2, random_state=0, stratify=y
    )
    learner = LogisticRegression(random_state=0, solver="liblinear").fit(x_train, y_train)
    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        factual_plugin=plugin_id,
        seed=0,
    )

    explanations = explainer.explain_factual(x_test[:2])
    assert explanations.explanations
    assert len(explanations.explanations) == 2
    assert all(explanation is not None for explanation in explanations.explanations)
    assert explainer.plugin_manager.explanation_plugin_identifiers["factual"] == plugin_id
