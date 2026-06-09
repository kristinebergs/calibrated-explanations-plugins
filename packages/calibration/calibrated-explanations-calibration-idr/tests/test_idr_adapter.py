"""Unit tests for the upstream isodistrreg IDR adapter."""

import os

import pytest

np = pytest.importorskip("numpy")
from ce_calibration_idr.idr_adapter import IDRDistributionAdapter  # noqa: E402


class FakeIDR:
    """Small fake with the subset of isodistrreg.IDR used by the adapter."""

    def __init__(self, *, X: np.ndarray, y: np.ndarray) -> None:
        """Store sorted calibration pairs."""
        self.X = np.asarray(X, dtype=float).reshape(-1)
        self.y = np.asarray(y, dtype=float)
        self.y_min = float(np.min(self.y))
        self.y_max = float(np.max(self.y))

    def cdf_at(self, X: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
        """Return a monotone logistic-like fake CDF for adapter tests."""
        x = np.asarray(X, dtype=float).reshape(-1)
        t = np.asarray(thresholds, dtype=float).reshape(-1)
        return 1.0 / (1.0 + np.exp(-(t - x)))

    def quantile(self, X: np.ndarray, probabilities: float) -> np.ndarray:
        """Return fake quantiles shifted away from raw scores."""
        x = np.asarray(X, dtype=float).reshape(-1)
        return np.clip(x + float(probabilities) + 1.0, self.y_min, self.y_max)


def fitted_adapter(monkeypatch: pytest.MonkeyPatch) -> IDRDistributionAdapter:
    """Return a deterministic fitted adapter for tests."""
    monkeypatch.setattr(IDRDistributionAdapter, "_load_idr_class", staticmethod(lambda: FakeIDR))
    scores = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0, 40.0])
    return IDRDistributionAdapter().fit(scores, y)


def test_should_reject_non_1d_scores(monkeypatch):
    adapter = fitted_adapter(monkeypatch)
    with pytest.raises(ValueError, match="one-dimensional"):
        adapter.fit(np.zeros((5, 2)), np.zeros(5))


def test_should_reject_mismatched_lengths(monkeypatch):
    adapter = fitted_adapter(monkeypatch)
    with pytest.raises(ValueError, match="same number"):
        adapter.fit(np.zeros(5), np.zeros(4))


def test_should_reject_quantile_before_fit():
    adapter = IDRDistributionAdapter()
    with pytest.raises(RuntimeError, match="fitted"):
        adapter.quantile(np.zeros(3), 0.5)


def test_should_reject_invalid_alpha(monkeypatch):
    adapter = fitted_adapter(monkeypatch)
    with pytest.raises(ValueError, match="alpha"):
        adapter.quantile(np.zeros(3), 1.5)


def test_should_reject_unknown_backend_without_fallback():
    with pytest.raises(ImportError, match="IDR backend is not installed"):
        IDRDistributionAdapter(backend="legacy-cps")


def test_should_return_ordered_quantiles_and_bounded_cdf(monkeypatch):
    adapter = fitted_adapter(monkeypatch)
    scores = np.array([0.2, 1.8, 2.9])
    low = adapter.quantile(scores, 0.05)
    predict = adapter.quantile(scores, 0.5)
    high = adapter.quantile(scores, 0.95)
    prob = adapter.cdf(scores, 25.0)
    assert np.all(low <= predict)
    assert np.all(predict <= high)
    assert np.all((0.0 <= prob) & (prob <= 1.0))


def test_should_use_real_isodistrreg_when_installed():
    if os.environ.get("CE_IDR_REQUIRE_REAL_BACKEND") == "1":
        __import__("isodistrreg")
    else:
        pytest.importorskip("isodistrreg")
    adapter = IDRDistributionAdapter().fit(
        np.array([0.0, 1.0, 2.0, 3.0]),
        np.array([0.0, 1.0, 2.0, 3.0]),
    )
    scores = np.array([0.5, 2.5])
    low = adapter.quantile(scores, 0.1)
    predict = adapter.quantile(scores, 0.5)
    high = adapter.quantile(scores, 0.9)
    prob = adapter.cdf(scores, 1.5)
    assert np.all(low <= predict)
    assert np.all(predict <= high)
    assert np.all((0.0 <= prob) & (prob <= 1.0))
