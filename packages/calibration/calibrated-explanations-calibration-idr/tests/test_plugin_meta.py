"""Plugin metadata tests for IDR calibration package."""

import os

import pytest
from ce_calibration_idr.metadata import PLUGIN_META


def test_should_expose_regression_interval_capability():
    assert PLUGIN_META["capabilities"] == ["interval:regression"]


def test_plugin_meta_validates_against_ce_contract():
    if os.environ.get("CE_IDR_REQUIRE_REAL_BACKEND") == "1":
        from calibrated_explanations.plugins import base  # noqa: E402
    else:
        base = pytest.importorskip("calibrated_explanations.plugins.base")
    base.validate_plugin_meta(PLUGIN_META)


def test_plugin_class_uses_metadata_single_source():
    pytest.importorskip("numpy")
    from ce_calibration_idr import IDRRegressionIntervalCalibratorPlugin  # noqa: E402

    plugin = IDRRegressionIntervalCalibratorPlugin()
    assert plugin.plugin_meta is PLUGIN_META


def test_metadata_declares_threshold_probability_calibrator_policy():
    assert PLUGIN_META["requires_probability_interval_calibrator"] is True
    assert (
        PLUGIN_META["default_probability_interval_calibrator"]
        == "official.calibration.venn_abers"
    )
    assert (
        PLUGIN_META["threshold_probability_calibrator_role"]
        == "binary_event_probability_interval"
    )
