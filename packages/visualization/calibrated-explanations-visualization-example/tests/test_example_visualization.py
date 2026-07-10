import sys
import warnings
from pathlib import Path

# Insert source tree before venv so coverage tracks source files, not the installed wheel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

pytest.importorskip("calibrated_explanations")

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import CalibratedExplainer

BOOTSTRAP_ID = "official.visualization.example.bootstrap"
BUILDER_ID = "official.visualization.example.builder"
RENDERER_ID = "official.visualization.example.renderer"
STYLE_ID = "official.example"


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()
    clear_warnings = getattr(registry, "clear_trust_warnings", None)
    if callable(clear_warnings):
        clear_warnings()


def test_visualization_plugin_should_register_style_and_render(monkeypatch):
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "ce_visualization_example.plugin:ExampleVisualizationBootstrap",
                BOOTSTRAP_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    _reset_registry_state()
    registry.load_entrypoint_plugins(include_untrusted=False)

    builder_descriptor = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_descriptor = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    assert builder_descriptor is not None
    assert builder_descriptor.trusted is True
    assert renderer_descriptor is not None
    assert renderer_descriptor.trusted is True
    assert style_descriptor is not None
    assert style_descriptor.metadata["builder_id"] == BUILDER_ID
    assert style_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None

    x, y = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=0, stratify=y)
    learner = LogisticRegression(random_state=0, solver="liblinear").fit(x_train, y_train)
    explainer = CalibratedExplainer(learner, x_train, y_train, mode="classification", seed=0)

    explanations = explainer.explain_factual(x_test[:1])
    assert len(explanations.explanations) == 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plot_result = explanations.plot(style=STYLE_ID, show=False)
    assert plot_result is not None
    assert not [
        str(item.message)
        for item in caught
        if "falling back to default" in str(item.message).lower()
        or "failed to find plot renderer" in str(item.message).lower()
    ]
