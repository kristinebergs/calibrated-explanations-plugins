"""Root conftest.py for calibrated-explanations-plugins tests."""
import calibrated_explanations.plugins.registry as registry
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_plugin_trust():
    """Ensure official plugins are trusted for tests."""
    # Trust the official plugins
    official_plugins = [
        "official.calibration.example",
        "official.explanation.factual.example",
    ]
    
    try:
        for plugin_id in official_plugins:
            registry.trust_plugin(plugin_id)
    except Exception:
        pass
