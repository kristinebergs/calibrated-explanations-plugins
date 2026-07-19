"""Single source of distribution-level plugin identity.

``PACKAGE_VERSION`` is the distribution version and is what every component's
``plugin_meta["version"]`` must report (CE's public ``validate_plugin_meta``
treats ``version`` as the plugin version, not an artifact schema version).
It is kept equal to ``project.version`` in ``pyproject.toml`` by
``tests/test_package_contract.py``.

Artifact schema versions are deliberately separate: each style module keeps
its own ``ARTIFACT_VERSION`` constant that versions the artifact payload
contract, independent of the distribution release cadence.

``PROVIDER`` identifies who publishes and maintains these components. It is
the plugin monorepo, not the Plotly organisation; earlier releases used
``"plotly.local"`` which could be misread as an upstream Plotly identity.
"""

PACKAGE_VERSION = "0.3.2"
PROVIDER = "calibrated-explanations-plugins"
