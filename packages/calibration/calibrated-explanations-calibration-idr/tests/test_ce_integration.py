"""End-to-end CE lifecycle tests for the IDR calibration plugin."""

import os

import pytest

if os.environ.get("CE_IDR_REQUIRE_REAL_BACKEND") == "1":
    np = __import__("numpy")
    __import__("sklearn")
    __import__("isodistrreg")
    ce = __import__("calibrated_explanations")
else:
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    pytest.importorskip("isodistrreg")
    ce = pytest.importorskip("calibrated_explanations")

from ce_calibration_idr import IDRRegressionIntervalCalibratorPlugin  # noqa: E402
from sklearn.datasets import make_regression  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

WrapCalibratedExplainer = getattr(ce, "WrapCalibratedExplainer", None)
if WrapCalibratedExplainer is None:
    pytest.skip(
        "WrapCalibratedExplainer is not available in this CE version",
        allow_module_level=True,
    )


def _data():
    X, y = make_regression(n_samples=120, n_features=4, noise=3.0, random_state=0)
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X,
        y,
        test_size=0.4,
        random_state=0,
    )
    X_cal, X_test, y_cal, _ = train_test_split(
        X_holdout,
        y_holdout,
        test_size=0.5,
        random_state=0,
    )
    return X_train, y_train, X_cal, y_cal, X_test


def test_idr_plugin_ce_owned_fit_lifecycle_regression_interval():
    """Exercise the CE-owned fitting pattern through explain_factual."""
    X_train, y_train, X_cal, y_cal, X_test = _data()
    plugin_id = IDRRegressionIntervalCalibratorPlugin.plugin_meta["name"]
    model = RandomForestRegressor(random_state=0)
    explainer = WrapCalibratedExplainer(model)
    explainer.fit(X_train, y_train)
    explainer.calibrate(X_cal, y_cal, interval_calibrator=plugin_id)
    explanations = explainer.explain_factual(X_test[:3], low_high_percentiles=(5, 95))
    assert explanations is not None


def test_idr_plugin_prefit_lifecycle_regression_interval():
    """Exercise the pre-fitted model pattern without calling explainer.fit(...)."""
    X_train, y_train, X_cal, y_cal, X_test = _data()
    plugin_id = IDRRegressionIntervalCalibratorPlugin.plugin_meta["name"]
    model = RandomForestRegressor(random_state=0).fit(X_train, y_train)
    explainer = WrapCalibratedExplainer(model)
    explainer.calibrate(X_cal, y_cal, interval_calibrator=plugin_id)
    explanations = explainer.explain_factual(X_test[:3], low_high_percentiles=(5, 95))
    assert explanations is not None


def test_idr_plugin_ce_owned_fit_lifecycle_threshold_probability():
    """Exercise thresholded regression through explain_factual."""
    X_train, y_train, X_cal, y_cal, X_test = _data()
    plugin_id = IDRRegressionIntervalCalibratorPlugin.plugin_meta["name"]
    model = RandomForestRegressor(random_state=0)
    explainer = WrapCalibratedExplainer(model)
    explainer.fit(X_train, y_train)
    explainer.calibrate(X_cal, y_cal, interval_calibrator=plugin_id)
    explanations = explainer.explain_factual(X_test[:3], threshold=float(np.median(y_cal)))
    assert explanations is not None


def test_plugin_conforms_to_ce_interval_plugin_protocol():
    """Assert CE recognizes the plugin object as an interval calibrator plugin."""
    from calibrated_explanations.plugins.intervals import IntervalCalibratorPlugin  # noqa: E402

    plugin = IDRRegressionIntervalCalibratorPlugin()
    assert isinstance(plugin, IntervalCalibratorPlugin)
