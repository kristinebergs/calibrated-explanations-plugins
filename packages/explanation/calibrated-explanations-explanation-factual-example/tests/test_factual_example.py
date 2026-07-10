import sys
from pathlib import Path

# Insert source tree before venv so coverage tracks source files, not the installed wheel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unittest.mock import Mock

import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

pytest.importorskip("calibrated_explanations")

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import CalibratedExplainer
from calibrated_explanations.core.config_manager import ConfigManager
from calibrated_explanations.plugins.base import validate_plugin_config
from calibrated_explanations.plugins.explanations import ExplanationContext
from calibrated_explanations.plugins.manager import PluginManager
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
    # Purge cached plugin module so load_entrypoint_plugins re-imports it fresh
    # and module-level register_factual_example_plugin() runs again.
    for key in list(sys.modules.keys()):
        if key.startswith("ce_explanation_factual_example"):
            del sys.modules[key]


class _DelegateStub:
    def initialize(self, context):
        self.context = context

    def supports(self, model):
        return True

    def supports_mode(self, mode, *, task):
        return mode == "factual" and task == "classification"

    def explain_batch(self, x, request):
        raise AssertionError("not needed for config tests")


def _context_with_plugin_config(plugin_config):
    return ExplanationContext(
        task="classification",
        mode="factual",
        feature_names=("f1",),
        categorical_features=(),
        categorical_labels={},
        discretizer=None,
        helper_handles={},
        predict_bridge=None,
        interval_settings={},
        plot_settings={},
        plugin_config=plugin_config,
    )


def test_example_plugin_receives_config_through_runtime_context():
    plugin = FactualExampleExplanationPlugin()
    plugin._delegate = _DelegateStub()
    context = _context_with_plugin_config(
        {"label_prefix": "runtime", "enabled_labels": ["positive", "negative"]}
    )

    plugin.initialize(context)

    assert plugin.last_plugin_config == {
        "label_prefix": "runtime",
        "enabled_labels": ("positive", "negative"),
    }


def test_example_plugin_config_schema_applies_defaults():
    schema = FactualExampleExplanationPlugin.plugin_meta["config_schema"]

    resolved = validate_plugin_config(
        plugin_id=FactualExampleExplanationPlugin.plugin_meta["name"],
        config={},
        schema=schema,
    )

    assert resolved["label_prefix"] == "example"
    assert resolved["enabled_labels"] == ()


def test_example_plugin_config_binds_pyproject_values_after_trust_resolution():
    plugin_id = FactualExampleExplanationPlugin.plugin_meta["name"]
    config_manager = ConfigManager(
        env_snapshot={},
        pyproject_snapshot={
            "plugins": {},
            "explanations": {},
            "intervals": {},
            "plots": {},
            "telemetry": {},
            "plugin_configs": {
                plugin_id: {"label_prefix": "pyproject", "enabled_labels": ["approved"]}
            },
        },
    )
    manager = PluginManager(Mock(), config_manager=config_manager)
    plugin = FactualExampleExplanationPlugin()

    resolved = manager.bind_plugin_config(plugin_id, plugin)

    assert resolved["label_prefix"] == "pyproject"
    assert resolved["enabled_labels"] == ("approved",)


def test_example_plugin_config_rejects_invalid_values():
    schema = FactualExampleExplanationPlugin.plugin_meta["config_schema"]

    with pytest.raises(Exception, match="enabled_labels"):
        validate_plugin_config(
            plugin_id=FactualExampleExplanationPlugin.plugin_meta["name"],
            config={"enabled_labels": "not-a-list"},
            schema=schema,
        )


def test_template_validator_rejects_malformed_provisional_config_schema():
    from scripts.validate_repo_structure import validate_plugin_config_schema

    errors = []
    validate_plugin_config_schema(
        Path("packages/explanation/calibrated-explanations-explanation-factual-example").resolve(),
        {"version": 1, "keys": {"enabled_labels": {"type": "not-supported"}}},
        errors,
    )

    assert any("type" in error for error in errors)


def test_example_plugin_config_export_redacts_sensitive_values():
    plugin_id = FactualExampleExplanationPlugin.plugin_meta["name"]
    config_manager = ConfigManager(
        env_snapshot={},
        pyproject_snapshot={
            "plugins": {},
            "explanations": {},
            "intervals": {},
            "plots": {},
            "telemetry": {},
            "plugin_configs": {plugin_id: {"diagnostic_token": "secret-token"}},
        },
    )

    export = config_manager.export_effective(
        plugin_config_schemas={
            plugin_id: FactualExampleExplanationPlugin.plugin_meta["config_schema"]
        }
    )

    redacted_config = export.values[f"effective.plugin_config.{plugin_id}"]
    assert redacted_config["diagnostic_token"] == "<redacted>"


def test_explanation_plugin_should_be_discoverable_and_runtime_valid(monkeypatch):
    plugin_id = FactualExampleExplanationPlugin.plugin_meta["name"]
    trust_ids = [
        plugin_id,
        "ce_explanation_factual_example.plugin:FactualExampleExplanationPlugin",
    ]
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
    x_train, x_test, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=0, stratify=y)
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
