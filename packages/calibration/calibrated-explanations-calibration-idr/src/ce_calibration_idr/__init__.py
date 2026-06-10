"""IDR regression interval calibration plugin for calibrated-explanations."""

from __future__ import annotations

from typing import Any

__all__ = ["IDRRegressionIntervalCalibratorPlugin"]


def __getattr__(name: str) -> Any:
    """Lazily import plugin classes so metadata can be inspected without runtime deps."""
    if name == "IDRRegressionIntervalCalibratorPlugin":
        from ce_calibration_idr.plugin import IDRRegressionIntervalCalibratorPlugin

        return IDRRegressionIntervalCalibratorPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
