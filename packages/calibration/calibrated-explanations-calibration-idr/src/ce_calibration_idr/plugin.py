"""Public plugin class for IDR regression interval calibration."""

from __future__ import annotations

from importlib import import_module, util
from typing import Any

from ce_calibration_idr.calibrator import IDRRegressionIntervalCalibrator
from ce_calibration_idr.metadata import PLUGIN_META

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


class IDRRegressionIntervalCalibratorPlugin(IntervalCalibratorPlugin):
    """Post-hoc IDR regression distribution calibrator for CE.

    The plugin does not replace or fit the underlying regression learner. The learner is fitted
    by CE (``explainer.fit(...)``) or supplied pre-fitted, and this plugin is fitted during
    ``explainer.calibrate(...)`` from calibration pairs of raw learner predictions and targets.
    Ordinary regression returns calibrated y-space quantiles. Thresholded regression converts the
    calibrated distribution into event scores and delegates final probability intervals to CE's
    Venn-Abers probability calibrator supplied by the CE context.
    """

    plugin_meta = PLUGIN_META

    def __init__(self, *, idr_backend: str = "isodistrreg") -> None:
        """Create the plugin without mutating CE registry or trust state."""
        self.idr_backend = idr_backend

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
    ) -> IDRRegressionIntervalCalibrator:
        """Create the IDR regression interval calibrator for a CE context."""
        self._require_regression_context(context)
        return IDRRegressionIntervalCalibrator(
            context=context,
            idr_backend=self.idr_backend,
            fast=fast,
        )

    @classmethod
    def _require_regression_context(cls, context: Any) -> None:
        task = cls._task_name(context)
        if task not in {"regression", "probabilistic_regression"}:
            raise TypeError(
                "IDRRegressionIntervalCalibratorPlugin only supports regression tasks; "
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
            "IDRRegressionIntervalCalibratorPlugin is an interval calibrator, "
            "not an explanation plugin."
        )
