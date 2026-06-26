"""Metadata and plugin contract tests for the conformal IDR calibration plugin."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from ce_calibration_idr.metadata import CONFORMAL_PLUGIN_META

# ---------------------------------------------------------------------------
# 1. Metadata validation
# ---------------------------------------------------------------------------


def test_conformal_plugin_meta_name():
    assert CONFORMAL_PLUGIN_META["name"] == "official.calibration.conformal_idr_regression"


def test_conformal_plugin_meta_has_regression_interval_capability():
    assert "interval:regression" in CONFORMAL_PLUGIN_META["capabilities"]


def test_conformal_plugin_meta_declares_coverage_type():
    assert CONFORMAL_PLUGIN_META["coverage_type"] == "split_conformal_marginal"


def test_conformal_plugin_meta_declares_threshold_probability_calibrator_policy():
    assert CONFORMAL_PLUGIN_META["requires_probability_interval_calibrator"] is True
    assert (
        CONFORMAL_PLUGIN_META["default_probability_interval_calibrator"]
        == "official.calibration.venn_abers"
    )
    assert (
        CONFORMAL_PLUGIN_META["threshold_probability_calibrator_role"]
        == "binary_event_probability_interval"
    )


def test_conformal_plugin_meta_validates_against_ce_contract():
    if os.environ.get("CE_IDR_REQUIRE_REAL_BACKEND") == "1":
        from calibrated_explanations.plugins import base
    else:
        base = pytest.importorskip("calibrated_explanations.plugins.base")
    base.validate_plugin_meta(CONFORMAL_PLUGIN_META)


def test_conformal_plugin_class_uses_metadata_single_source():
    pytest.importorskip("numpy")
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    plugin = ConformalIDRRegressionIntervalCalibratorPlugin()
    assert plugin.plugin_meta is CONFORMAL_PLUGIN_META


# ---------------------------------------------------------------------------
# Plain IDR metadata is unchanged
# ---------------------------------------------------------------------------


def test_plain_idr_metadata_unchanged():
    from ce_calibration_idr.metadata import PLUGIN_META

    assert PLUGIN_META["name"] == "official.calibration.idr_regression"
    assert "coverage_type" not in PLUGIN_META


def test_plain_idr_plugin_class_still_uses_original_meta():
    pytest.importorskip("numpy")
    from ce_calibration_idr import IDRRegressionIntervalCalibratorPlugin
    from ce_calibration_idr.metadata import PLUGIN_META

    plugin = IDRRegressionIntervalCalibratorPlugin()
    assert plugin.plugin_meta is PLUGIN_META


# ---------------------------------------------------------------------------
# Plugin constructor validation
# ---------------------------------------------------------------------------


def test_plugin_raises_when_only_idr_x_provided():  # noqa: N802
    pytest.importorskip("numpy")
    import numpy as np
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    with pytest.raises(ValueError, match="both"):
        ConformalIDRRegressionIntervalCalibratorPlugin(idr_X=np.ones((5, 2)))


def test_plugin_raises_when_only_idr_y_provided():
    pytest.importorskip("numpy")
    import numpy as np
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    with pytest.raises(ValueError, match="both"):
        ConformalIDRRegressionIntervalCalibratorPlugin(idr_y=np.ones(5))


def test_plugin_accepts_both_idr_x_and_idr_y():  # noqa: N802
    pytest.importorskip("numpy")
    import numpy as np
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    plugin = ConformalIDRRegressionIntervalCalibratorPlugin(
        idr_X=np.ones((5, 2)),
        idr_y=np.ones(5),
    )
    assert plugin.idr_X is not None
    assert plugin.idr_y is not None


def test_plugin_accepts_no_external_idr_data():
    pytest.importorskip("numpy")
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin  # noqa: I001

    plugin = ConformalIDRRegressionIntervalCalibratorPlugin()
    assert plugin.idr_X is None
    assert plugin.idr_y is None


# ---------------------------------------------------------------------------
# Task name inference (mirrors plain IDR plugin tests)
# ---------------------------------------------------------------------------


def test_conformal_plugin_infers_regression_from_context_without_mode():
    pytest.importorskip("numpy")
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    context = SimpleNamespace(
        learner=SimpleNamespace(predict=lambda x: x),
        metadata={"operation": "initialize"},
    )
    assert ConformalIDRRegressionIntervalCalibratorPlugin._task_name(context) == "regression"


def test_conformal_plugin_supports_regression_task():
    pytest.importorskip("numpy")
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    plugin = ConformalIDRRegressionIntervalCalibratorPlugin()
    context = SimpleNamespace(
        learner=SimpleNamespace(predict=lambda x: x),
        mode="regression",
    )
    assert plugin.supports(context) is True


def test_conformal_plugin_rejects_explain_call():
    pytest.importorskip("numpy")
    from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

    plugin = ConformalIDRRegressionIntervalCalibratorPlugin()
    with pytest.raises(NotImplementedError, match="interval calibrator"):
        plugin.explain(None, None)
