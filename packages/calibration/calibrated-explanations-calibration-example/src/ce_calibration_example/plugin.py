from __future__ import annotations

from typing import Any

from calibrated_explanations.plugins.builtins import LegacyIntervalCalibratorPlugin
from calibrated_explanations.plugins.intervals import IntervalCalibratorContext, IntervalCalibratorPlugin
from calibrated_explanations.plugins.registry import find_interval_descriptor, register_interval_plugin, trust_plugin


class ExampleIntervalCalibratorPlugin(IntervalCalibratorPlugin):
    """Runtime-valid interval calibrator that delegates to CE's legacy backend.

    The example stays intentionally small:

    1. expose ``plugin_meta`` so CE can discover and trust it,
    2. register the plugin descriptor on import, and
    3. forward ``create(...)`` to CE's builtin interval calibrator.
    """

    plugin_meta = {
        "schema_version": 1,
        "name": "official.calibration.example",
        "version": "0.1.0",
        "provider": "official",
        "capabilities": ["interval:classification"],
        "modes": ("classification",),
        "dependencies": ("core.interval.legacy",),
        "trusted": True,
        "trust": False,
        "confidence_source": "legacy-delegate",
        "requires_bins": False,
        "fast_compatible": False,
    }

    def create(self, context: IntervalCalibratorContext, *, fast: bool = False) -> Any:
        """Return the same interval calibrator CE would normally use internally."""
        delegate = LegacyIntervalCalibratorPlugin()
        return delegate.create(context, fast=fast)


def register_example_interval_plugin() -> None:
    """Register the example interval plugin descriptor when imported via entry points."""
    identifier = str(ExampleIntervalCalibratorPlugin.plugin_meta["name"])
    if find_interval_descriptor(identifier) is not None:
        return
    register_interval_plugin(
        identifier,
        ExampleIntervalCalibratorPlugin(),
        source="entrypoint",
    )
    # Explicitly trust the plugin after registration
    try:
        trust_plugin(identifier)
    except Exception:
        pass


register_example_interval_plugin()
