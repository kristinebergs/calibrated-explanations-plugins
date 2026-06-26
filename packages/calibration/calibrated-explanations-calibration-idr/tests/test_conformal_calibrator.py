"""Unit tests for the conformal IDR regression interval calibrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from ce_calibration_idr.conformal_calibrator import (  # noqa: E402
    ConformalIDRRegressionIntervalCalibrator,
    _conformal_quantile,
)
from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402

# ---------------------------------------------------------------------------
# Fake primitives shared by all tests
# ---------------------------------------------------------------------------


class FakeIDR:
    """Deterministic IDR fake whose quantile shifts scores by (alpha + 1)."""

    def __init__(self, *, X: np.ndarray, y: np.ndarray) -> None:  # noqa: N803
        self.X = np.asarray(X, dtype=float).reshape(-1)
        self.y = np.asarray(y, dtype=float)
        self.y_min = float(np.min(self.y))
        self.y_max = float(np.max(self.y))
        self.fit_data = (X, y)

    def cdf_at(self, x_values: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
        x = np.asarray(x_values, dtype=float).reshape(-1)
        t = np.asarray(thresholds, dtype=float).reshape(-1)
        return 1.0 / (1.0 + np.exp(-(t - x)))

    def quantile(self, x_values: np.ndarray, probabilities: float) -> np.ndarray:
        x = np.asarray(x_values, dtype=float).reshape(-1)
        return np.clip(x + float(probabilities) + 1.0, self.y_min, self.y_max)


class LinearLearner:
    """Predict first column as scalar regression score."""

    def predict(self, x_values: Any) -> np.ndarray:
        return np.asarray(x_values, dtype=float)[:, 0]


class FakeVennAbers:
    """VA fake that visibly shifts event scores."""

    def __init__(self, scores: np.ndarray, labels: np.ndarray) -> None:
        self.scores = np.asarray(scores, dtype=float)
        self.labels = np.asarray(labels, dtype=int)

    def predict_proba(self, scores: np.ndarray, *, output_interval: bool) -> dict[str, np.ndarray]:
        base = np.clip(np.asarray(scores, dtype=float).reshape(-1) * 0.8 + 0.1, 0.0, 1.0)
        return {
            "predict": base,
            "low": np.maximum(0.0, base - 0.1),
            "high": np.minimum(1.0, base + 0.1),
        }


@dataclass
class Context:
    """Minimal CE-like interval calibrator context."""

    learner: LinearLearner
    X_cal: np.ndarray
    y_cal: np.ndarray
    mode: str = "regression"

    def venn_abers_factory(self, scores: np.ndarray, labels: np.ndarray) -> FakeVennAbers:
        return FakeVennAbers(scores, labels)


@dataclass
class ContextNoVA:
    """Context without Venn-Abers factory."""

    learner: LinearLearner
    X_cal: np.ndarray
    y_cal: np.ndarray
    mode: str = "regression"


@dataclass
class FrozenContext:
    """Context that tracks mutation attempts."""

    learner: LinearLearner
    X_cal: np.ndarray
    y_cal: np.ndarray
    mode: str = "regression"
    _mutations: list[str] = field(default_factory=list)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name in ("learner", "X_cal", "y_cal", "mode", "_mutations"):
            object.__setattr__(self, name, value)
        else:
            self._mutations.append(name)

    def venn_abers_factory(self, scores: np.ndarray, labels: np.ndarray) -> FakeVennAbers:
        return FakeVennAbers(scores, labels)


def _make_calibrator(  # noqa: N803
    monkeypatch: pytest.MonkeyPatch,
    *,
    idr_X: Any | None = None,  # noqa: N803
    idr_y: Any | None = None,
    n_cal: int = 60,
    idr_fraction: float = 0.5,
    random_state: int = 0,
    min_conformal_samples: int = 10,
) -> ConformalIDRRegressionIntervalCalibrator:
    """Return a fitted conformal calibrator with fake IDR backend."""
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    X_cal = np.arange(n_cal, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(2.0, 10.0, n_cal)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    return ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_X=idr_X,
        idr_y=idr_y,
        idr_fraction=idr_fraction,
        random_state=random_state,
        min_conformal_samples=min_conformal_samples,
    )


# ---------------------------------------------------------------------------
# _conformal_quantile helper
# ---------------------------------------------------------------------------


def test_conformal_quantile_returns_correct_value():
    scores = np.array([0.1, 0.5, 0.3, 0.8, 0.2])
    # alpha=0.2 -> k = ceil(6 * 0.8) = ceil(4.8) = 5 -> sorted[4] = 0.8
    result = _conformal_quantile(scores, alpha=0.2)
    assert result == pytest.approx(0.8)


def test_conformal_quantile_raises_for_too_small_set():
    scores = np.array([0.1, 0.2])
    # alpha=0.01 -> k = ceil(3 * 0.99) = ceil(2.97) = 3 > n=2
    with pytest.raises(ValueError, match="Calibration set has"):
        _conformal_quantile(scores, alpha=0.01)


def test_conformal_quantile_raises_for_non_finite_scores():
    with pytest.raises(ValueError, match="finite"):
        _conformal_quantile(np.array([0.1, np.inf]), alpha=0.1)


def test_conformal_quantile_raises_for_bad_alpha():
    with pytest.raises(ValueError, match="strictly between"):
        _conformal_quantile(np.array([0.1, 0.2, 0.3]), alpha=0.0)
    with pytest.raises(ValueError, match="strictly between"):
        _conformal_quantile(np.array([0.1, 0.2, 0.3]), alpha=1.0)


def test_conformal_quantile_raises_for_2d_scores():
    with pytest.raises(ValueError, match="one-dimensional"):
        _conformal_quantile(np.array([[0.1, 0.2], [0.3, 0.4]]), alpha=0.1)


def test_conformal_quantile_raises_for_empty_scores():
    with pytest.raises(ValueError, match="empty"):
        _conformal_quantile(np.array([]), alpha=0.1)


# ---------------------------------------------------------------------------
# 1. Metadata validation is tested in test_conformal_plugin_meta.py
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 2. External IDR data path
# ---------------------------------------------------------------------------


def test_external_idr_data_path_uses_separate_fit_data(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_train = np.arange(20, dtype=float).reshape(-1, 1)
    y_train = np.linspace(1.0, 5.0, 20)
    X_cal = np.arange(40, 80, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(5.0, 12.0, 40)

    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_X=X_train,
        idr_y=y_train,
    )

    assert cal._data_source == "external_idr_data"
    assert cal._n_idr == len(y_train)
    assert cal._n_conformal == len(y_cal)


def test_external_idr_data_path_conformal_uses_full_cal_set(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_train = np.arange(20, dtype=float).reshape(-1, 1)
    y_train = np.linspace(1.0, 5.0, 20)
    X_cal = np.arange(40, 80, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(5.0, 12.0, 40)

    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_X=X_train,
        idr_y=y_train,
    )

    assert len(cal._y_conf) == len(y_cal)


# ---------------------------------------------------------------------------
# 3. Fallback split path
# ---------------------------------------------------------------------------


def test_fallback_split_produces_disjoint_subsets(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_cal = np.arange(80, dtype=float).reshape(-1, 1)
    y_cal = np.arange(80, dtype=float)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.5,
        random_state=42,
        min_conformal_samples=10,
    )

    assert cal._data_source == "split_calibration_data"
    assert cal._n_idr + cal._n_conformal == len(y_cal)


def test_fallback_split_respects_idr_fraction(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    n = 100
    X_cal = np.arange(n, dtype=float).reshape(-1, 1)
    y_cal = np.arange(n, dtype=float)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.4,
        random_state=0,
        min_conformal_samples=10,
    )

    assert cal._n_idr == 40
    assert cal._n_conformal == 60


def test_fallback_split_raises_when_too_few_conformal_samples(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_cal = np.arange(30, dtype=float).reshape(-1, 1)
    y_cal = np.arange(30, dtype=float)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)

    with pytest.raises(ValueError, match="min_conformal_samples"):
        ConformalIDRRegressionIntervalCalibrator(
            context=ctx,
            idr_fraction=0.9,
            min_conformal_samples=25,
        )


# ---------------------------------------------------------------------------
# 4. Ordinary regression interval is conformalized
# ---------------------------------------------------------------------------


def test_regression_interval_includes_conformal_correction(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0], [5.0]]), low_high_percentiles=(5.0, 95.0))
    assert "conformal_qhat" in pred
    qhat = pred["conformal_qhat"][0]
    assert np.isfinite(qhat)
    assert qhat >= 0.0


def test_regression_interval_predict_is_idr_median(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    x_test = np.array([[1.0], [3.0], [5.0]])
    pred = cal.predict(x_test, low_high_percentiles=(5.0, 95.0))
    # IDR median = raw_score + 0.5 + 1.0
    expected_median = cal._raw_predict(x_test) + 0.5 + 1.0
    assert np.allclose(pred["predict"], np.clip(expected_median, cal._idr._y_min, cal._idr._y_max))


def test_regression_interval_ordering_holds(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0], [5.0], [10.0]]), low_high_percentiles=(5.0, 95.0))
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])


def test_predict_uncertainty_returns_ce_tuple(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    result = cal.predict_uncertainty(np.array([[1.0], [5.0]]), (5.0, 95.0))
    assert len(result) == 4
    assert result[3] is None
    predict, low, high, _ = result
    assert np.all(low <= predict)
    assert np.all(predict <= high)


# ---------------------------------------------------------------------------
# 5. Correction cache
# ---------------------------------------------------------------------------


def test_qhat_cache_is_reused_for_same_percentiles(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    cal.predict(np.array([[1.0]]), low_high_percentiles=(5.0, 95.0))
    assert (5.0, 95.0) in cal._qhat_cache
    cached_qhat = cal._qhat_cache[(5.0, 95.0)]
    cal.predict(np.array([[2.0]]), low_high_percentiles=(5.0, 95.0))
    # Same key — must be same value (no recomputation)
    assert cal._qhat_cache[(5.0, 95.0)] == cached_qhat


def test_different_percentile_pairs_produce_separate_qhat(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    cal.predict(np.array([[1.0]]), low_high_percentiles=(5.0, 95.0))
    cal.predict(np.array([[1.0]]), low_high_percentiles=(10.0, 90.0))
    assert (5.0, 95.0) in cal._qhat_cache
    assert (10.0, 90.0) in cal._qhat_cache
    # Different alpha leads to different qhat values generally
    assert len(cal._qhat_cache) == 2


# ---------------------------------------------------------------------------
# 6. One-sided upper interval
# ---------------------------------------------------------------------------


def test_one_sided_upper_interval_has_finite_floor(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0], [5.0]]), low_high_percentiles=(-np.inf, 90.0))
    assert np.all(np.isfinite(pred["low"]))
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])


def test_one_sided_upper_interval_high_receives_conformal_correction(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0]]), low_high_percentiles=(-np.inf, 90.0))
    qhat = pred["conformal_qhat"][0]
    assert qhat >= 0.0
    # Upper bound is U_test + qhat; qhat >= 0 so high >= U_test
    raw = cal._raw_predict(np.array([[1.0]]))
    U_test = cal._idr.quantile(raw, 0.9)
    assert pred["high"][0] >= U_test[0] - 1e-9


# ---------------------------------------------------------------------------
# 7. One-sided lower interval
# ---------------------------------------------------------------------------


def test_one_sided_lower_interval_has_finite_ceiling(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0], [5.0]]), low_high_percentiles=(10.0, np.inf))
    assert np.all(np.isfinite(pred["high"]))
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])


def test_one_sided_lower_interval_low_receives_conformal_correction(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0]]), low_high_percentiles=(10.0, np.inf))
    qhat = pred["conformal_qhat"][0]
    assert qhat >= 0.0
    raw = cal._raw_predict(np.array([[1.0]]))
    L_test = cal._idr.quantile(raw, 0.1)
    assert pred["low"][0] <= L_test[0] + 1e-9


# ---------------------------------------------------------------------------
# 8. Invalid percentile requests
# ---------------------------------------------------------------------------


def test_both_infinite_bounds_rejected(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    with pytest.raises(ValueError, match="infinite"):
        cal.predict(np.array([[1.0]]), low_high_percentiles=(-np.inf, np.inf))


def test_finite_percentile_outside_range_rejected(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    with pytest.raises(ValueError):
        cal.predict(np.array([[1.0]]), low_high_percentiles=(-5.0, 95.0))


def test_interval_not_bracketing_median_rejected(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    with pytest.raises(ValueError, match="bracket"):
        cal.predict(np.array([[1.0]]), low_high_percentiles=(60.0, 90.0))


def test_too_small_conformal_set_raises_during_quantile(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    # Very small conformal set and tight alpha -> k > n
    X_cal = np.arange(30, dtype=float).reshape(-1, 1)
    y_cal = np.arange(30, dtype=float)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.9,
        min_conformal_samples=1,
        min_idr_samples=2,
    )
    # n_conformal is 3; request alpha requiring k > 3
    with pytest.raises(ValueError, match="Calibration set has"):
        cal.predict(np.array([[1.0]]), low_high_percentiles=(1.0, 99.0))


# ---------------------------------------------------------------------------
# 9. Threshold mode uses held-out calibration data
# ---------------------------------------------------------------------------


def test_threshold_mode_with_external_idr_uses_full_cal_for_va(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_train = np.arange(20, dtype=float).reshape(-1, 1)
    y_train = np.linspace(1.0, 5.0, 20)
    n_cal = 50
    X_cal = np.arange(50, 100, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(5.0, 12.0, n_cal)

    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_X=X_train,
        idr_y=y_train,
    )

    # Threshold adapter's calibration data must be the full CE cal set
    assert len(cal._y_conf) == n_cal

    pred = cal.predict(np.array([[1.0], [5.0]]), threshold=7.0)
    assert np.all(pred["low"] >= 0.0)
    assert np.all(pred["low"] <= pred["predict"])
    assert np.all(pred["predict"] <= pred["high"])
    assert np.all(pred["high"] <= 1.0)


def test_threshold_mode_without_external_idr_uses_only_held_out(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    n_cal = 80
    X_cal = np.arange(n_cal, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(2.0, 12.0, n_cal)

    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)
    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.5,
        random_state=0,
        min_conformal_samples=10,
    )

    # Threshold adapter calibration must be smaller than full cal set
    assert cal._n_conformal < n_cal
    assert cal._n_conformal + cal._n_idr == n_cal

    pred = cal.predict(np.array([[1.0], [5.0]]), threshold=7.0)
    assert np.all(pred["low"] >= 0.0)
    assert np.all(pred["predict"] >= 0.0)
    assert np.all(pred["high"] <= 1.0)


# ---------------------------------------------------------------------------
# 10. Threshold mode delegates to Venn-Abers
# ---------------------------------------------------------------------------


def test_threshold_mode_predict_differs_from_raw_idr_event_score(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    pred = cal.predict(np.array([[1.0], [4.0]]), threshold=5.0)
    assert not np.allclose(pred["predict"], pred["event_score"])


# ---------------------------------------------------------------------------
# 11. Context immutability
# ---------------------------------------------------------------------------


def test_context_is_not_mutated(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_cal = np.arange(60, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(2.0, 10.0, 60)
    ctx = FrozenContext(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)

    ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.5,
        random_state=0,
        min_conformal_samples=10,
    )
    assert ctx._mutations == [], f"Context was mutated: {ctx._mutations}"


# ---------------------------------------------------------------------------
# 12. No silent fallback
# ---------------------------------------------------------------------------


def test_missing_isodistrreg_raises_import_error(monkeypatch):
    # Make _load_idr_class raise ImportError (simulating missing backend)
    def raise_import(*args: Any, **kwargs: Any) -> None:
        raise ImportError("isodistrreg is not installed")

    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(raise_import))

    X_cal = np.arange(60, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(2.0, 10.0, 60)
    ctx = Context(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)

    with pytest.raises(ImportError):
        ConformalIDRRegressionIntervalCalibrator(context=ctx, idr_fraction=0.5, random_state=0)


def test_threshold_mode_without_va_factory_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))

    X_cal = np.arange(60, dtype=float).reshape(-1, 1)
    y_cal = np.linspace(2.0, 10.0, 60)
    ctx = ContextNoVA(learner=LinearLearner(), X_cal=X_cal, y_cal=y_cal)

    cal = ConformalIDRRegressionIntervalCalibrator(
        context=ctx,
        idr_fraction=0.5,
        random_state=0,
        min_conformal_samples=10,
    )

    with pytest.raises(RuntimeError, match="Venn-Abers factory"):
        cal.predict(np.array([[1.0], [2.0]]), threshold=5.0)


# ---------------------------------------------------------------------------
# 13. insert_calibration
# ---------------------------------------------------------------------------


def test_insert_calibration_raises_not_implemented(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    with pytest.raises(NotImplementedError, match="refit/recalibration"):
        cal.insert_calibration(None, None)


# ---------------------------------------------------------------------------
# CE surface completeness
# ---------------------------------------------------------------------------


def test_calibrator_exposes_ce_regression_surface(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    for method_name in (
        "predict",
        "predict_probability",
        "predict_proba",
        "predict_uncertainty",
        "pre_fit_for_probabilistic",
        "compute_proba_cal",
        "insert_calibration",
        "is_multiclass",
        "is_mondrian",
    ):
        assert callable(getattr(cal, method_name))


def test_is_multiclass_returns_false(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    assert cal.is_multiclass() is False


def test_is_mondrian_returns_false(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    assert cal.is_mondrian() is False


def test_data_source_diagnostic_fields(monkeypatch):
    cal = _make_calibrator(monkeypatch, n_cal=60, min_conformal_samples=10)
    assert cal._data_source in ("external_idr_data", "split_calibration_data")
    assert isinstance(cal._n_idr, int)
    assert isinstance(cal._n_conformal, int)
    assert cal._n_idr >= 2
    assert cal._n_conformal >= 10
