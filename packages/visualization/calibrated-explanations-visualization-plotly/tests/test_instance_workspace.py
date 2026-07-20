from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations.plugins.plots import PlotRenderContext
from calibrated_explanations.utils.exceptions import ConfigurationError

STYLE_ID = "plotly.dashboard.instance_workspace"
BUILDER_ID = "official.visualization.plotly.dashboard.instance_workspace.builder"
RENDERER_ID = "official.visualization.plotly.dashboard.instance_workspace.renderer"
BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"


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


def _load_plugin(monkeypatch):
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
                BOOTSTRAP_ID,
                BUILDER_ID,
                RENDERER_ID,
            ]
        ),
    )
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _context(explanation, *, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "global"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "dashboard"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _install_fake_plotly(monkeypatch):
    class FakeScatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.layout = {}
            self.vlines = []
            self.hlines = []
            self.annotations = []

        @property
        def data(self):
            return tuple(self.traces)

        def add_trace(self, trace, **_kwargs):
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_hline(self, **kwargs):
            self.hlines.append(kwargs)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **_kwargs):
            pass

        def update_yaxes(self, **_kwargs):
            pass

        def to_html(self, **kwargs):
            return f'<div id="{kwargs.get("div_id", "fake")}">plotly</div>'

        def write_html(self, path):
            Path(path).write_text("<html><body>plotly</body></html>", encoding="utf-8")

        def show(self):
            pass

    def make_subplots(**kwargs):
        fig = FakeFigure()
        fig.layout.update(kwargs)
        return fig

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Figure = FakeFigure
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Bar = FakeScatter
    subplots_mod.make_subplots = make_subplots
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _factual_rules() -> dict:
    return {
        "weight": [2.0, -1.5],
        "weight_low": [1.8, -2.0],
        "weight_high": [2.3, -1.0],
        "rule": ["age > 30", "income <= 40"],
        "feature": [0, 1],
        "value": [31, 39],
        "feature_value": [31, 39],
    }


def _alternative_rules() -> dict:
    return {
        "feature": [0, 1],
        "feature_value": [31, 39],
        "rule": ["age <= 30", "income > 40"],
        "predict": [0.2, 0.3],
        "predict_low": [0.1, 0.2],
        "predict_high": [0.3, 0.4],
        "primary_role": ["counter", "super"],
        "rank": [1, 2],
    }


def _explanations(count: int = 3) -> SimpleNamespace:
    collection = SimpleNamespace(
        feature_names=["age", "income"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )
    factual = []
    alternatives = []
    for index in range(count):
        factual.append(
            SimpleNamespace(
                index=index,
                calibrated_explanations=collection,
                prediction={
                    "predict": 0.6 + index * 0.05,
                    "low": 0.5,
                    "high": 0.7 + index * 0.05,
                    "classes": 1,
                },
                rules=_factual_rules(),
                get_mode=lambda: "classification",
                is_probabilistic=lambda: True,
                is_regression=lambda: False,
                is_alternative=lambda: False,
            )
        )
        alternatives.append(
            SimpleNamespace(
                index=index,
                calibrated_explanations=collection,
                prediction={
                    "predict": 0.6 + index * 0.05,
                    "low": 0.5,
                    "high": 0.7 + index * 0.05,
                    "classes": 1,
                },
                rules=_alternative_rules(),
                get_rules=_alternative_rules,
                get_mode=lambda: "classification",
                is_probabilistic=lambda: True,
                is_regression=lambda: False,
                is_alternative=lambda: True,
            )
        )
    collection.explanations = factual
    collection.alternative_explanations = alternatives
    return collection


def test_registration_and_style_resolution(monkeypatch):
    _load_plugin(monkeypatch)

    assert registry.find_plot_builder_descriptor(BUILDER_ID) is not None
    assert registry.find_plot_renderer_descriptor(RENDERER_ID) is not None
    style = registry.find_plot_style_descriptor(STYLE_ID)
    assert style is not None
    assert style.metadata["builder_id"] == BUILDER_ID
    assert style.metadata["renderer_id"] == RENDERER_ID


def test_standalone_none_precomputes_global_only(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_explanations(), precompute="none"))

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["dashboard_mode"] == "standalone_html"
    assert artifact["precomputed_local"] == {}
    assert artifact["global_artifact"]["artifact_type"] == "plotly.global.instance_explorer"
    assert artifact["metadata"]["limitation"].startswith("Standalone mode can inspect")


def test_selected_precompute_uses_registry_cards_and_aliases(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    # The SimpleNamespace fixture lacks rank_features, so the ensured card's
    # deterministic rank fallback fires its documented visible warning.
    with pytest.warns(UserWarning, match="rank_features unavailable"):
        artifact = plugin.build(
            _context(
                _explanations(),
                precompute="selected",
                selected_instance_indices=[1],
                available_cards=["local_uncertainty_quadrant", "local_ensured"],
            )
        )

    local = artifact["precomputed_local"]["1"]
    assert local["instance_index"] == 1
    assert [card["card_id"] for card in local["cards"]] == ["uncertainty_quadrant", "ensured"]
    assert all(card["available"] for card in local["cards"])


def test_all_precompute_enforces_hard_guard(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    with pytest.raises(ConfigurationError, match="max_precomputed_instances"):
        plugin.build(_context(_explanations(3), precompute="all", max_precomputed_instances=2))


def test_renderer_exports_standalone_html(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _explanations(),
        precompute="selected",
        selected_instance_indices=[0],
        available_cards=["local_uncertainty_quadrant"],
        path=tmp_path / "workspace",
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert result.saved_paths == (str(tmp_path / "workspace.html"),)
    html = Path(result.saved_paths[0]).read_text(encoding="utf-8")
    assert "Standalone mode can inspect precomputed explanations only" in html
    assert "ce-instance-overview" in html
    assert "Uncertainty Quadrant" in html


class _BridgeLearner:
    def predict_proba(self, _x):
        return []


class _BridgeExplainer:
    learner = _BridgeLearner()
    class_labels = None

    def __init__(self):
        self.factual_calls = []
        self.alternative_calls = []

    def predict_proba(self, x, **kwargs):
        assert "style" not in kwargs
        rows = len(x)
        proba = [[0.4, 0.6 + index * 0.05] for index in range(rows)]
        low = [[0.3, 0.5] for _ in range(rows)]
        high = [[0.5, 0.8 + index * 0.05] for index in range(rows)]
        return proba, (low, high)

    def explain_factual(self, x, **kwargs):
        assert "style" not in kwargs
        self.factual_calls.append((x, kwargs))
        collection = SimpleNamespace(
            feature_names=["age", "income"],
            batch_metadata={"task": "classification", "mode": "classification"},
        )
        local = SimpleNamespace(
            index=0,
            calibrated_explanations=collection,
            prediction={"predict": 0.6, "low": 0.5, "high": 0.8, "classes": 1},
            rules=_factual_rules(),
            get_mode=lambda: "classification",
            is_probabilistic=lambda: True,
            is_regression=lambda: False,
            is_alternative=lambda: False,
        )
        collection.explanations = [local]
        return collection

    def explore_alternatives(self, x, **kwargs):
        assert "style" not in kwargs
        self.alternative_calls.append((x, kwargs))
        collection = SimpleNamespace(
            feature_names=["age", "income"],
            batch_metadata={"task": "classification", "mode": "classification"},
        )
        local = SimpleNamespace(
            index=0,
            calibrated_explanations=collection,
            prediction={"predict": 0.6, "low": 0.5, "high": 0.8, "classes": 1},
            rules=_alternative_rules(),
            get_rules=_alternative_rules,
            get_mode=lambda: "classification",
            is_probabilistic=lambda: True,
            is_regression=lambda: False,
            is_alternative=lambda: True,
        )
        collection.explanations = [local]
        return collection


def test_dashboard_builder_precomputes_via_runtime_context(monkeypatch, tmp_path):
    """CE >=1.0.0rc2 native dispatch: the builder reads the originating
    explainer/x/threshold from ``context.runtime`` (no ``_ce_compat`` bridge
    involved) and precomputes local explanations directly."""
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)

    explainer = _BridgeExplainer()
    context = PlotRenderContext(
        explanation=None,
        instance_metadata=MappingProxyType({"type": "global"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "dashboard"}),
        show=False,
        path=str(tmp_path / "workspace"),
        save_ext=None,
        options=MappingProxyType(
            {
                "dashboard_mode": "standalone_html",
                "precompute": "selected",
                "selected_instance_indices": [1],
                "available_cards": ["local_factual_bars", "alternative_feature_summary"],
                "low_high_percentiles": (20, 80),
                # CE's reserved global payload (see plotting._dispatch_explicit_global_plot_style):
                # the instance-explorer sub-build consumes this via
                # options.get("payload"), not context.explanation, once forwarded
                # into global_options by the dashboard builder.
                "payload": {
                    "proba": [[0.4, 0.6], [0.3, 0.7]],
                    "predict": None,
                    "low": [0.5, 0.6],
                    "high": [0.7, 0.8],
                    "is_regularized": True,
                },
            }
        ),
        runtime=MappingProxyType(
            {
                "scope": "global",
                "explainer": explainer,
                "x": [[1, 2], [3, 4]],
                "threshold": None,
                "bins": [10, 20],
            }
        ),
    )

    plugin = registry.find_plot_plugin(STYLE_ID)
    artifact = plugin.build(context)

    assert len(explainer.factual_calls) == 1
    assert len(explainer.alternative_calls) == 1
    factual_row, factual_kwargs = explainer.factual_calls[0]
    alternative_row, alternative_kwargs = explainer.alternative_calls[0]
    assert factual_row.tolist() == [[3, 4]]
    assert alternative_row.tolist() == [[3, 4]]
    assert factual_kwargs["low_high_percentiles"] == (20, 80)
    assert alternative_kwargs["low_high_percentiles"] == (20, 80)
    assert factual_kwargs["bins"].tolist() == [20]
    assert alternative_kwargs["bins"].tolist() == [20]
    assert artifact["instance_records"][1]["metadata"]["percentiles"] == (20, 80)
    assert all(card["available"] is True for card in artifact["precomputed_local"]["1"]["cards"])


def test_registration_never_patches_plot_global_or_ce_classes(monkeypatch):
    """CE >=1.0.0rc2: registration must not touch ``plotting.plot_global`` or
    any CE class method -- the former ``_ce_compat`` bridge is gone."""
    plugin_module = _load_plugin(monkeypatch)
    import calibrated_explanations.plotting as ce_plotting
    from calibrated_explanations.core.calibrated_explainer import CalibratedExplainer
    from calibrated_explanations.core.wrap_explainer import WrapCalibratedExplainer

    original_plot_global = ce_plotting.plot_global
    plugin_module.register_plotly_visualization_components()

    assert ce_plotting.plot_global is original_plot_global
    assert not hasattr(ce_plotting.plot_global, "_plotly_bridge_version")
    assert not hasattr(CalibratedExplainer.plot, "_plotly_bridge_version")
    assert not hasattr(WrapCalibratedExplainer.plot, "_plotly_bridge_version")


def test_dashboard_html_treats_hostile_labels_as_text(monkeypatch, tmp_path):
    """Hostile class labels/targets must never reach the DOM as executable HTML.

    Covers both channels: the server-side JSON payload (HTML-escaped inside the
    data script tag) and the client-side summary panel (which must build DOM
    nodes via textContent, never innerHTML string concatenation).
    """
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    hostile = "<img src=x onerror=alert('xss')>"
    hostile_script = "</script><script>alert('xss')</script>"

    artifact = plugin.build(
        _context(
            _explanations(),
            precompute="none",
            global_options={"true_labels": [hostile, hostile_script, "benign"]},
        )
    )
    records = artifact["instance_records"]
    assert any(record.get("true_label") == hostile for record in records)

    workspace = importlib.import_module("ce_visualization_plotly.instance_workspace")
    html_content = workspace.build_dashboard_html(artifact)

    assert hostile not in html_content, "hostile label must be HTML-escaped everywhere"
    assert "</script><script>alert" not in html_content
    # Regression guard: the summary panel must not be assembled via innerHTML
    # from data values.
    assert "summary.innerHTML" not in html_content
    assert "textContent" in html_content
