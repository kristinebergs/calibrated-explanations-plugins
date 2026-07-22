import numpy as np
import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

pytest.importorskip("calibrated_explanations")

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import CalibratedExplainer
from ce_calibration_example import ExampleIntervalCalibratorPlugin


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    # CE 1.0.0 removed clear_env_trust_cache()/clear_trust_warnings() without a
    # replacement, and the process-level ConfigManager singleton snapshots
    # os.environ once and never re-reads it, so a monkeypatched
    # CE_TRUST_PLUGIN has no effect unless both the singleton and the
    # registry's own env-trust cache are reset (see
    # development/oss_ce_upstream_log.md).
    from calibrated_explanations.core.config_manager import (
        reset_process_config_manager_for_testing,
    )

    reset_process_config_manager_for_testing()
    registry._ENV_TRUST_CACHE = None
    registry._PYPROJECT_TRUST_CACHE = None


@pytest.mark.xfail(
    reason=(
        "CE 1.0.0 bug (unpatched, upstream): "
        "calibrated_explanations.plugins.registry.load_entrypoint_plugins() routes any "
        "entry-point plugin with a 'modes' key into register_explanation_plugin() instead of "
        "the interval catalog (registry.py, 'if \"modes\" in meta:' branch). "
        "validate_interval_metadata() now requires 'modes' on interval plugins too (raises "
        "'plugin_meta missing required key: modes' if omitted), so every entry-point-discovered "
        "interval calibrator plugin is misrouted and never appears in find_interval_descriptor(). "
        "Confirmed: capabilities=['interval:classification'] has no effect on the routing "
        "decision, only 'modes' presence does. Direct registration via register_interval_plugin() "
        "(this package's own import-time side effect) is unaffected; only the standard "
        "entry-point rediscovery path this test exercises is broken. Do not work around this in "
        "the plugin; fix must land in CE."
    ),
    strict=True,
)
def test_interval_plugin_should_be_discoverable_and_runtime_valid(monkeypatch):
    plugin_id = ExampleIntervalCalibratorPlugin.plugin_meta["name"]
    trust_ids = [plugin_id, "ce_calibration_example.plugin:ExampleIntervalCalibratorPlugin"]
    monkeypatch.setenv("CE_TRUST_PLUGIN", ",".join(trust_ids))
    _reset_registry_state()
    registry.load_entrypoint_plugins(include_untrusted=False)

    descriptor = registry.find_interval_descriptor(plugin_id)
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
        interval_plugin=plugin_id,
        seed=0,
    )

    prediction = explainer.predict(x_test[:3], calibrated=True)
    assert np.asarray(prediction).shape == (3,)
    probability = explainer.predict_proba(x_test[:3], calibrated=True)
    assert np.asarray(probability[0]).shape[0] == 3
    assert explainer.plugin_manager.interval_plugin_identifiers["default"] == plugin_id
