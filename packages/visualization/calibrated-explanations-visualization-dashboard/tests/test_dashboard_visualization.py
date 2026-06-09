from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest
from calibrated_explanations import CalibratedExplainer
from sklearn.datasets import make_classification, make_regression
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split

matplotlib.use("Agg")

from calibrated_explanations.plugins.plots import PlotRenderContext, PlotRenderResult

STYLE_ID = "official.visualization.dashboard"
BUILDER_ID = "official.visualization.dashboard.builder"
RENDERER_ID = "official.visualization.dashboard.renderer"

_PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")


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


def _dummy_collection() -> SimpleNamespace:
    """Minimal collection with SHAP metadata, mirroring the factual-shap test fixture."""
    return SimpleNamespace(
        batch_metadata={
            "shap": {
                "feature_names": ["a", "b", "c"],
                "data": [[1.0, 2.0, 3.0], [1.5, 2.5, 3.5]],
                "values": {
                    "center": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                    "lower": [[0.05, 0.1, 0.15], [0.2, 0.25, 0.3]],
                    "upper": [[0.15, 0.3, 0.45], [0.6, 0.75, 0.9]],
                    "uncertainty": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                },
                "base_values": {
                    "center": [0.2, 0.2],
                    "lower": [0.1, 0.1],
                    "upper": [0.3, 0.3],
                    "uncertainty": [0.2, 0.2],
                },
                "_runtime": {"explanations": {}},
            }
        },
        explanations=[
            SimpleNamespace(
                to_narrative=lambda expertise_level="beginner", output_format="text": (
                    f"Narrative at {expertise_level} level."
                ),
            )
        ],
    )


def _trust_env(*extra_ids: str) -> str:
    return ",".join(
        [
            "ce_visualization_dashboard.plugin:DashboardVisualizationBootstrap",
            STYLE_ID,
            BUILDER_ID,
            RENDERER_ID,
            *extra_ids,
        ]
    )


def _white_png_bytes() -> bytes:
    """1×1 white PNG bytes for stub panels."""
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.axis("off")
    import io

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _make_stub_matplotlib_figure() -> object:
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, 1])
    return fig


def _make_stub_plugin(figure_factory=None):
    """Create a minimal PlotBuilder+Renderer stub."""

    class _StubBuilder:
        plugin_meta = {
            "schema_version": 1,
            "name": "stub.builder",
            "version": "0.1.0",
            "provider": "test",
            "style": "stub.style",
            "output_formats": ("png",),
            "capabilities": ["plot:plotspec"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "legacy_compatible": False,
            "default_renderer": "stub.renderer",
        }

        def build(self, context):
            return {"stub": True}

    class _StubRenderer:
        plugin_meta = {
            "schema_version": 1,
            "name": "stub.renderer",
            "version": "0.1.0",
            "provider": "test",
            "output_formats": ("png",),
            "capabilities": ["plot:renderer"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "supports_interactive": False,
        }

        def render(self, artifact, *, context):
            fig = figure_factory() if figure_factory else _make_stub_matplotlib_figure()
            return PlotRenderResult(artifact=artifact, figure=fig, saved_paths=())

    return _StubBuilder(), _StubRenderer()


def _register_stub_style(monkeypatch) -> None:
    from calibrated_explanations.plugins.registry import (
        register_plot_builder,
        register_plot_renderer,
        register_plot_style,
    )

    builder, renderer = _make_stub_plugin()
    register_plot_builder("stub.builder", builder, source="manual")
    register_plot_renderer("stub.renderer", renderer, source="manual")
    register_plot_style(
        "stub.style",
        metadata={
            "style": "stub.style",
            "builder_id": "stub.builder",
            "renderer_id": "stub.renderer",
            "fallbacks": (),
            "legacy_compatible": False,
            "is_default": False,
            "default_for": (),
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_builder_raises_for_unregistered_style(monkeypatch):
    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [{"style": "nonexistent.style"}]}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    assert plugin is not None
    with pytest.raises(RuntimeError, match="nonexistent.style"):
        plugin.build(context)


def test_builder_returns_dict_not_plotspec(monkeypatch):
    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [], "narrative": False}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    assert isinstance(artifact, dict)
    assert "explanation" in artifact
    assert "plots" in artifact
    assert "narrative" in artifact


def test_renderer_empty_plots_with_narrative(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [], "narrative": True, "expertise_level": "beginner"}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 0
    assert result.extras["narrative"] is True


def test_renderer_single_stub_plugin(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()
    _register_stub_style(monkeypatch)

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [{"style": "stub.style"}], "narrative": False}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1
    assert result.extras["narrative"] is False


def test_renderer_two_plugins(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()
    _register_stub_style(monkeypatch)

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": "stub.style"}, {"style": "stub.style"}],
                "narrative": False,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 2


def test_renderer_sub_plugin_exception_produces_placeholder(monkeypatch):
    import plotly.graph_objects as go
    from calibrated_explanations.plugins.registry import (
        register_plot_builder,
        register_plot_renderer,
        register_plot_style,
    )

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    # Register a plugin whose renderer always raises
    class _BrokenBuilder:
        plugin_meta = {
            "schema_version": 1,
            "name": "broken.builder",
            "version": "0.1.0",
            "provider": "test",
            "style": "broken.style",
            "output_formats": ("png",),
            "capabilities": ["plot:plotspec"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "legacy_compatible": False,
            "default_renderer": "broken.renderer",
        }

        def build(self, context):
            return {}

    class _BrokenRenderer:
        plugin_meta = {
            "schema_version": 1,
            "name": "broken.renderer",
            "version": "0.1.0",
            "provider": "test",
            "output_formats": ("png",),
            "capabilities": ["plot:renderer"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "supports_interactive": False,
        }

        def render(self, artifact, *, context):
            raise RuntimeError("intentional failure")

    register_plot_builder("broken.builder", _BrokenBuilder(), source="manual")
    register_plot_renderer("broken.renderer", _BrokenRenderer(), source="manual")
    register_plot_style(
        "broken.style",
        metadata={
            "style": "broken.style",
            "builder_id": "broken.builder",
            "renderer_id": "broken.renderer",
            "fallbacks": (),
            "legacy_compatible": False,
            "is_default": False,
            "default_for": (),
        },
    )

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [{"style": "broken.style"}], "narrative": False}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    # Dashboard still returns a valid figure with placeholder panel
    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1


def test_renderer_sub_plugin_exception_raises_when_strict(monkeypatch):
    from calibrated_explanations.plugins.registry import (
        register_plot_builder,
        register_plot_renderer,
        register_plot_style,
    )

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    class _BrokenBuilder:
        plugin_meta = {
            "schema_version": 1,
            "name": "broken.strict.builder",
            "version": "0.1.0",
            "provider": "test",
            "style": "broken.strict.style",
            "output_formats": ("png",),
            "capabilities": ["plot:plotspec"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "legacy_compatible": False,
            "default_renderer": "broken.strict.renderer",
        }

        def build(self, context):
            return {}

    class _BrokenRenderer:
        plugin_meta = {
            "schema_version": 1,
            "name": "broken.strict.renderer",
            "version": "0.1.0",
            "provider": "test",
            "output_formats": ("png",),
            "capabilities": ["plot:renderer"],
            "dependencies": (),
            "trusted": True,
            "trust": True,
            "supports_interactive": False,
        }

        def render(self, artifact, *, context):
            raise RuntimeError("strict failure")

    register_plot_builder("broken.strict.builder", _BrokenBuilder(), source="manual")
    register_plot_renderer("broken.strict.renderer", _BrokenRenderer(), source="manual")
    register_plot_style(
        "broken.strict.style",
        metadata={
            "style": "broken.strict.style",
            "builder_id": "broken.strict.builder",
            "renderer_id": "broken.strict.renderer",
            "fallbacks": (),
            "legacy_compatible": False,
            "is_default": False,
            "default_for": (),
        },
    )

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": "broken.strict.style"}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)

    with pytest.raises(RuntimeError, match="strict failure"):
        plugin.render(artifact, context=context)


def test_renderer_narrative_fallback(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")
    layout_mod = importlib.import_module("ce_visualization_dashboard.layout")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    original_render_narrative = layout_mod.render_narrative_panel

    def _failing_narrative(explanation, expertise_level):
        raise RuntimeError("narrative engine unavailable")

    monkeypatch.setattr(layout_mod, "render_narrative_panel", _failing_narrative)

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [], "narrative": True}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)

    # Renderer catches the RuntimeError from monkeypatched render_narrative_panel;
    # the dashboard should still return a go.Figure (narrative panel shows fallback).
    # However since we patched layout_mod directly the error will propagate unless
    # layout.render_narrative_panel itself handles it. It does — it has a try/except.
    # But we replaced it with a version that raises. Let's verify the renderer handles it.
    result = plugin.render(artifact, context=context)
    assert isinstance(result.figure, go.Figure)

    monkeypatch.setattr(layout_mod, "render_narrative_panel", original_render_narrative)


def test_renderer_save_html(tmp_path, monkeypatch):
    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    save_base = str(tmp_path / "dashboard")
    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=save_base,
        save_ext=".html",
        options=MappingProxyType({"plots": [], "narrative": True, "title": "Test"}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert len(result.saved_paths) == 1
    assert result.saved_paths[0].endswith(".html")
    html_file = Path(result.saved_paths[0])
    assert html_file.exists()
    assert html_file.stat().st_size > 0


def test_result_figure_is_plotly_figure(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType({"plots": [], "narrative": True}),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)


def test_registration_idempotent(monkeypatch):
    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()
    plugin_mod.register_dashboard_visualization_components()  # second call — no error

    assert registry.find_plot_builder_descriptor(BUILDER_ID) is not None
    assert registry.find_plot_renderer_descriptor(RENDERER_ID) is not None
    assert registry.find_plot_style_descriptor(STYLE_ID) is not None


def test_result_extras_contain_panels_and_narrative(monkeypatch):
    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()
    _register_stub_style(monkeypatch)

    context = PlotRenderContext(
        explanation=_dummy_collection(),
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {"plots": [{"style": "stub.style"}], "narrative": True, "expertise_level": "advanced"}
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert "n_panels" in result.extras
    assert "narrative" in result.extras
    assert result.extras["n_panels"] == 1
    assert result.extras["narrative"] is True


# ---------------------------------------------------------------------------
# CE-default sub-style tests (factual and alternative, real CE explainer)
# ---------------------------------------------------------------------------

CE_DEFAULT_STYLE_ID = "official.visualization.dashboard.ce_default"
CE_DEFAULT_BUILDER_ID = "official.visualization.dashboard.ce_default.builder"
CE_DEFAULT_RENDERER_ID = "official.visualization.dashboard.ce_default.renderer"


def _trust_env_ce_default() -> str:
    return _trust_env(CE_DEFAULT_STYLE_ID, CE_DEFAULT_BUILDER_ID, CE_DEFAULT_RENDERER_ID)


@lru_cache(maxsize=None)
def _build_case_explanations(case_name: str, explanation_kind: str):
    """Build real CE explanations for a scenario/kind pair."""
    if case_name == "binary_classification":
        X, y = make_classification(n_samples=120, n_features=4, random_state=0)
        X_train, X_test, y_train, _ = train_test_split(
            X, y, test_size=0.2, random_state=0, stratify=y
        )
        model = LogisticRegression(random_state=0, solver="liblinear").fit(X_train, y_train)
        explainer = CalibratedExplainer(model, X_train, y_train, mode="classification", seed=0)
        return (
            explainer.explain_factual(X_test[:2])
            if explanation_kind == "factual"
            else explainer.explore_alternatives(X_test[:2])
        )

    if case_name == "multiclass_classification":
        X, y = make_classification(
            n_samples=150,
            n_features=6,
            n_classes=3,
            n_informative=4,
            n_redundant=0,
            n_clusters_per_class=1,
            random_state=0,
        )
        X_train, X_test, y_train, _ = train_test_split(
            X, y, test_size=0.2, random_state=0, stratify=y
        )
        model = LogisticRegression(random_state=0, max_iter=500).fit(X_train, y_train)
        explainer = CalibratedExplainer(model, X_train, y_train, mode="classification", seed=0)
        return (
            explainer.explain_factual(X_test[:2])
            if explanation_kind == "factual"
            else explainer.explore_alternatives(X_test[:2])
        )

    if case_name == "regression":
        X, y = make_regression(n_samples=120, n_features=4, noise=0.1, random_state=0)
        X_train, X_test, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=0)
        model = LinearRegression().fit(X_train, y_train)
        explainer = CalibratedExplainer(model, X_train, y_train, mode="regression", seed=0)
        return (
            explainer.explain_factual(X_test[:2])
            if explanation_kind == "factual"
            else explainer.explore_alternatives(X_test[:2])
        )

    if case_name == "probabilistic_regression":
        X, y = make_regression(n_samples=120, n_features=4, noise=0.1, random_state=7)
        X_train, X_test, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=0)
        model = LinearRegression().fit(X_train, y_train)
        explainer = CalibratedExplainer(model, X_train, y_train, mode="regression", seed=0)
        threshold = float(np.median(y_train))
        return (
            explainer.explain_factual(X_test[:2], threshold=threshold)
            if explanation_kind == "factual"
            else explainer.explore_alternatives(X_test[:2], threshold=threshold)
        )

    raise ValueError(f"Unknown case_name {case_name!r}")


@pytest.fixture(scope="module")
def real_factual_explanations():
    return _build_case_explanations("binary_classification", "factual")


@pytest.fixture(scope="module")
def real_alternative_explanations():
    return _build_case_explanations("binary_classification", "alternative")


def test_ce_default_factual_collection_per_instance(monkeypatch, real_factual_explanations):
    """Collection + per_instance=True (default) → one dashboard figure per instance."""
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    n_instances = len(real_factual_explanations.explanations)
    context = PlotRenderContext(
        explanation=real_factual_explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    # per_instance=True: one plotly Figure per instance; first is result.figure,
    # the rest are in extras["extra_figures"].
    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_instances"] == n_instances
    assert len(result.extras["extra_figures"]) == n_instances - 1
    # Each per-instance dashboard has exactly 1 panel (one ce_default plot).
    assert result.extras["n_panels"] == 1
    plt.close("all")


def test_ce_default_factual_collection_combined(monkeypatch, real_factual_explanations):
    """Collection + per_instance=False → one combined dashboard for all instances."""
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    context = PlotRenderContext(
        explanation=real_factual_explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "per_instance": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    # No per-instance split — single figure, no extra_figures key.
    assert "extra_figures" not in result.extras
    n_instances = len(real_factual_explanations.explanations)
    assert result.extras["n_panels"] == n_instances
    plt.close("all")


def test_ce_default_factual_single_instance(monkeypatch, real_factual_explanations):
    """Single instance passed (CE-style indexing) → exactly one panel."""
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    # Select the instance by indexing, as CE's own API requires.
    single_exp = real_factual_explanations[0]
    context = PlotRenderContext(
        explanation=single_exp,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1
    plt.close("all")


def test_ce_default_alternative_collection_per_instance(monkeypatch, real_alternative_explanations):
    """Alternative collection + per_instance=True → one dashboard per instance."""
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    n_instances = len(real_alternative_explanations.explanations)
    context = PlotRenderContext(
        explanation=real_alternative_explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "alternative"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_instances"] == n_instances
    assert len(result.extras["extra_figures"]) == n_instances - 1
    assert result.extras["n_panels"] == 1
    plt.close("all")


def test_ce_default_alternative_single_instance(monkeypatch, real_alternative_explanations):
    """Single alternative instance (CE-style indexing) → exactly one panel."""
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    single_exp = real_alternative_explanations[0]
    context = PlotRenderContext(
        explanation=single_exp,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "alternative"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1
    plt.close("all")


def test_ce_default_with_narrative(monkeypatch, real_factual_explanations):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    single_exp = real_factual_explanations[0]
    context = PlotRenderContext(
        explanation=single_exp,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": True,
                "expertise_level": "beginner",
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1
    assert result.extras["narrative"] is True
    plt.close("all")


def test_ce_default_ce_style_forwarded(monkeypatch, real_factual_explanations):
    """ce_style in the plot spec is forwarded as style= to explanation.plot()."""

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    captured_kwargs: dict = {}

    original_plot = real_factual_explanations.explanations[0].plot.__func__

    def _spy_plot(self, filter_top=None, **kwargs):
        captured_kwargs.update(kwargs)
        return original_plot(self, filter_top=filter_top, **kwargs)

    monkeypatch.setattr(
        type(real_factual_explanations.explanations[0]),
        "plot",
        _spy_plot,
    )

    single_exp = real_factual_explanations[0]
    context = PlotRenderContext(
        explanation=single_exp,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID, "ce_style": "ensured"}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    plugin.render(artifact, context=context)

    assert captured_kwargs.get("style") == "ensured"
    assert "ce_style" not in captured_kwargs
    plt.close("all")


@pytest.mark.parametrize(
    ("case_name", "explanation_kind", "intent_type"),
    [
        ("binary_classification", "factual", "factual"),
        ("binary_classification", "alternative", "alternative"),
        ("multiclass_classification", "factual", "factual"),
        ("multiclass_classification", "alternative", "alternative"),
        ("regression", "factual", "factual"),
        ("regression", "alternative", "alternative"),
        ("probabilistic_regression", "factual", "factual"),
        ("probabilistic_regression", "alternative", "alternative"),
    ],
)
def test_ce_default_all_modes_collection_per_instance(
    monkeypatch, case_name, explanation_kind, intent_type
):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    explanations = _build_case_explanations(case_name, explanation_kind)
    n_instances = len(explanations.explanations)
    context = PlotRenderContext(
        explanation=explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_instances"] == n_instances
    assert len(result.extras["extra_figures"]) == n_instances - 1
    assert result.extras["n_panels"] == 1
    plt.close("all")


@pytest.mark.parametrize(
    ("case_name", "explanation_kind", "intent_type"),
    [
        ("binary_classification", "factual", "factual"),
        ("binary_classification", "alternative", "alternative"),
        ("multiclass_classification", "factual", "factual"),
        ("multiclass_classification", "alternative", "alternative"),
        ("regression", "factual", "factual"),
        ("regression", "alternative", "alternative"),
        ("probabilistic_regression", "factual", "factual"),
        ("probabilistic_regression", "alternative", "alternative"),
    ],
)
def test_ce_default_all_modes_collection_combined(
    monkeypatch, case_name, explanation_kind, intent_type
):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    explanations = _build_case_explanations(case_name, explanation_kind)
    n_instances = len(explanations.explanations)
    context = PlotRenderContext(
        explanation=explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "per_instance": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert "extra_figures" not in result.extras
    assert result.extras["n_panels"] == n_instances
    plt.close("all")


@pytest.mark.parametrize(
    ("case_name", "explanation_kind", "intent_type"),
    [
        ("binary_classification", "factual", "factual"),
        ("binary_classification", "alternative", "alternative"),
        ("multiclass_classification", "factual", "factual"),
        ("multiclass_classification", "alternative", "alternative"),
        ("regression", "factual", "factual"),
        ("regression", "alternative", "alternative"),
        ("probabilistic_regression", "factual", "factual"),
        ("probabilistic_regression", "alternative", "alternative"),
    ],
)
def test_ce_default_all_modes_single_instance(
    monkeypatch, case_name, explanation_kind, intent_type
):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    single_exp = _build_case_explanations(case_name, explanation_kind)[0]
    context = PlotRenderContext(
        explanation=single_exp,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    assert result.extras["n_panels"] == 1
    plt.close("all")


def test_combined_narrative_renders_per_instance_blocks_and_scroll(monkeypatch):
    import plotly.graph_objects as go

    sys.path.insert(0, _PKG_SRC)
    plugin_mod = importlib.import_module("ce_visualization_dashboard.plugin")

    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env_ce_default())
    _reset_registry_state()
    plugin_mod.register_dashboard_visualization_components()

    explanations = _build_case_explanations("probabilistic_regression", "factual")
    context = PlotRenderContext(
        explanation=explanations,
        instance_metadata=MappingProxyType({}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "factual"}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(
            {
                "plots": [{"style": CE_DEFAULT_STYLE_ID}],
                "narrative": True,
                "expertise_level": "beginner",
                "per_instance": False,
                "strict_subplots": True,
            }
        ),
    )
    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert isinstance(result.figure, go.Figure)
    annotations = list(result.figure.layout.annotations or [])
    assert len(annotations) >= 2
    narrative_text = "\n".join(str(annotation.text) for annotation in annotations)
    assert "Instance 1" in narrative_text
    assert "Instance 2" in narrative_text
    assert "overflow-y:auto" in narrative_text
    plt.close("all")
