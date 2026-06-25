"""Public plugin class for split-conformalized IDR regression interval calibration."""

from __future__ import annotations

from importlib import import_module, util
from typing import Any

from ce_calibration_idr.conformal_calibrator import ConformalIDRRegressionIntervalCalibrator
from ce_calibration_idr.metadata import CONFORMAL_PLUGIN_META

_HAS_CE = util.find_spec("calibrated_explanations") is not None
_HAS_INTERVALS = _HAS_CE and util.find_spec("calibrated_explanations.plugins.intervals") is not None

if _HAS_INTERVALS:
    _intervals = import_module("calibrated_explanations.plugins.intervals")
    IntervalCalibratorContext = _intervals.IntervalCalibratorContext
    IntervalCalibratorPlugin = _intervals.IntervalCalibratorPlugin
else:  # pragma: no cover - package unit tests run without CE installed.
    IntervalCalibratorContext = Any  # type: ignore[misc,assignment]

    class IntervalCalibratorPlugin:  # type: ignore[no-redef]
        """Minimal protocol placeholder used only when CE is unavailable in unit tests."""


class ConformalIDRRegressionIntervalCalibratorPlugin(IntervalCalibratorPlugin):
    """Split-conformalized IDR regression interval calibrator plugin for CE.

    This plugin reuses the IDR distribution backend but adds a held-out split-conformal
    correction for ordinary regression intervals. The conformal correction provides a
    finite-sample marginal coverage guarantee under exchangeability of held-out calibration
    examples and future test examples.

    The guarantee is marginal only. Conditional coverage is not claimed. IDR itself does
    not have conformal validity; the conformal guarantee comes from the held-out correction
    applied on top of IDR quantiles.

    Two data regimes are supported:

    **Preferred (external IDR data)**: Supply ``idr_X`` and ``idr_y`` (typically the
    training set). IDR is fitted on this external data. The full CE calibration set is
    used for conformal correction and threshold-mode Venn-Abers calibration.

    **Fallback (internal split)**: Omit ``idr_X``/``idr_y``. The CE calibration set is
    split into an IDR-fit subset and a held-out subset. Only the held-out subset is used
    for conformal correction and Venn-Abers threshold calibration. This is less efficient
    when calibration data is scarce.

    Threshold mode returns probability intervals, not y-space intervals.
    """

    plugin_meta = CONFORMAL_PLUGIN_META

    def __init__(  # noqa: N803
        self,
        *,
        idr_X: Any | None = None,  # noqa: N803
        idr_y: Any | None = None,
        idr_backend: str = "isodistrreg",
        idr_fraction: float = 0.5,
        random_state: int | None = None,
        min_idr_samples: int = 2,
        min_conformal_samples: int = 20,
    ) -> None:
        """Create the plugin without mutating CE registry or trust state.

        Parameters
        ----------
        idr_X:
            Optional external IDR-fit feature matrix. Must be supplied together with
            ``idr_y``. When provided, IDR is fitted on this data and the full CE
            calibration set is used for conformal correction.
        idr_y:
            Optional external IDR-fit target vector. Must be supplied together with
            ``idr_X``.
        idr_backend:
            IDR backend identifier. Currently only ``"isodistrreg"`` is supported.
        idr_fraction:
            Fraction of the CE calibration set to use for IDR fitting in fallback
            split mode. The remainder is used for conformal correction. Ignored when
            ``idr_X``/``idr_y`` are provided.
        random_state:
            Random state for the calibration set split in fallback split mode.
        min_idr_samples:
            Minimum required samples for the IDR-fit subset in fallback split mode.
        min_conformal_samples:
            Minimum required samples for the held-out conformal subset in fallback
            split mode.
        """
        if (idr_X is None) != (idr_y is None):
            raise ValueError("idr_X and idr_y must both be provided or both omitted.")
        self.idr_X = idr_X
        self.idr_y = idr_y
        self.idr_backend = idr_backend
        self.idr_fraction = idr_fraction
        self.random_state = random_state
        self.min_idr_samples = min_idr_samples
        self.min_conformal_samples = min_conformal_samples

    def supports(self, model: Any) -> bool:
        """Return whether this plugin can be considered for a regression model."""
        task = self._task_name(model)
        if task is None:
            return True
        return task in {"regression", "probabilistic_regression"}

    def create(
        self,
        context: IntervalCalibratorContext,
        *,
        fast: bool = False,
    ) -> ConformalIDRRegressionIntervalCalibrator:
        """Create the conformal IDR regression interval calibrator for a CE context."""
        self._require_regression_context(context)
        return ConformalIDRRegressionIntervalCalibrator(
            context=context,
            idr_X=self.idr_X,
            idr_y=self.idr_y,
            idr_backend=self.idr_backend,
            idr_fraction=self.idr_fraction,
            random_state=self.random_state,
            min_idr_samples=self.min_idr_samples,
            min_conformal_samples=self.min_conformal_samples,
        )

    @classmethod
    def _require_regression_context(cls, context: Any) -> None:
        task = cls._task_name(context)
        if task not in {"regression", "probabilistic_regression"}:
            raise TypeError(
                "ConformalIDRRegressionIntervalCalibratorPlugin only supports regression tasks; "
                f"received {task!r}."
            )

    @staticmethod
    def _task_name(candidate: Any) -> str | None:
        for attr in ("task", "mode", "calibration_kind"):
            value = getattr(candidate, attr, None)
            if value is None:
                continue
            value = getattr(value, "value", value)
            return str(value).lower()
        metadata = getattr(candidate, "metadata", None)
        if isinstance(metadata, dict):
            for key in ("task", "mode", "calibration_kind"):
                value = metadata.get(key)
                if value is None:
                    continue
                value = getattr(value, "value", value)
                return str(value).lower()
        learner = getattr(candidate, "learner", None)
        if learner is not None and not hasattr(learner, "predict_proba"):
            return "regression"
        return None

    def explain(self, model: Any, x: Any, **kwargs: Any) -> Any:
        """Reject direct explanation calls because this is an interval calibrator plugin."""
        raise NotImplementedError(
            "ConformalIDRRegressionIntervalCalibratorPlugin is an interval calibrator, "
            "not an explanation plugin."
        )
