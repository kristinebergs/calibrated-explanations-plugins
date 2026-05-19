from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations.plugins.plots import PlotRenderContext

STYLE_ID = "plotly.local.alternative_feature_summary"
BUILDER_ID = "official.visualization.plotly.local.alternative_feature_summary.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_feature_summary.renderer"
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
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
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
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "alternative"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def _install_fake_plotly(monkeypatch):
    class FakeTrace:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeBar(FakeTrace):
        pass

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.annotations = []
            self.layout = {}
            self.xaxes = []
            self.yaxes = []
            self.shown = False
            self.html_paths = []

        @property
        def data(self):
            return tuple(self.traces)

        def add_trace(self, trace, row=None, col=None):
            trace.kwargs["row"] = row
            trace.kwargs["col"] = col
            self.traces.append(trace)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **kwargs):
            self.xaxes.append(kwargs)

        def update_yaxes(self, **kwargs):
            self.yaxes.append(kwargs)

        def write_html(self, path, **_kwargs):
            self.html_paths.append(path)
            Path(path).write_text("<html><body>plotly</body></html>", encoding="utf-8")

        def show(self):
            self.shown = True

    def make_subplots(**kwargs):
        figure = FakeFigure()
        figure.layout["subplot_titles"] = kwargs.get("subplot_titles")
        figure.layout["rows"] = kwargs.get("rows")
        return figure

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Bar = FakeBar
    graph_objects_mod.Figure = FakeFigure
    subplots_mod.make_subplots = make_subplots
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _rules() -> dict:
    return {
        "feature": [0, 0, 1, [0, 2], 2, 3],
        "feature_value": [10, 10, 20, [10, 30], 30, 40],
        "rule": [
            "f0 <= 10",
            "f0 > 8",
            "f1 <= 20",
            "f0 <= 10 AND f2 > 30",
            "f2 <= 30",
            "semifactual candidate",
        ],
        "predict": [0.2, 0.3, 0.8, 0.1, 0.7, 0.6],
        "predict_low": [0.1, 0.2, 0.7, 0.0, 0.6, 0.5],
        "predict_high": [0.3, 0.4, 0.9, 0.2, 0.8, 0.7],
        "primary_role": ["counter", "counterfactual", "superfactual", "counter", None, None],
        "is_ensured": [False, True, False, True, True, False],
        "is_pareto": [False, True, True, False, False, False],
        "rank": [1, 2, 3, 4, 5, 6],
    }


def _dummy_alternative_explanation(*, rules: dict | None = None) -> SimpleNamespace:
    payload = rules or _rules()
    collection = SimpleNamespace(
        feature_names=["feat0", "feat1", "feat2", "feat3"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.75, "low": 0.66, "high": 0.84, "classes": 1.0},
        rules=payload,
        conjunctive_rules=None,
        has_conjunctive_rules=False,
        get_rules=lambda: payload,
        get_mode=lambda: "classification",
        is_probabilistic=lambda: True,
        is_regression=lambda: False,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]
    return collection


def test_registration_and_trusted_style_resolution(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)

    assert registry.find_plot_builder_descriptor(BUILDER_ID).trusted is True
    assert registry.find_plot_renderer_descriptor(RENDERER_ID).trusted is True
    assert style_descriptor is not None
    assert style_descriptor.metadata["builder_id"] == BUILDER_ID
    assert style_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


def test_builder_creates_rule_records_and_feature_summaries(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation()))

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["artifact_version"] == "0.2.0"
    assert artifact["rule_records"]
    assert artifact["feature_summaries"]
    assert artifact["metadata"]["created_by"] == STYLE_ID
    assert artifact["panel_config"]["show_conjunctions"] is False


def test_role_quality_combinations_are_counted_explicitly(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation()))
    feat0 = next(
        summary for summary in artifact["feature_summaries"] if summary["feature_name"] == "feat0"
    )

    assert feat0["primary_role_counts"]["counter"] == 3
    assert feat0["role_quality_counts"]["counter"] == 1
    assert feat0["role_quality_counts"]["counter__ensured"] == 1
    assert feat0["role_quality_counts"]["counter__ensured__pareto"] == 1
    assert "counter__ensured__pareto" in artifact["role_quality_keys"]


def test_deterministic_role_quality_key_order(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation()))

    expected_order = [
        "counter",
        "counter__ensured",
        "counter__ensured__pareto",
        "super__pareto",
        "unknown",
        "unknown__ensured",
    ]
    assert artifact["role_quality_keys"] == expected_order


def test_unknown_role_fallback_and_infer_role_option(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    default_artifact = plugin.build(_context(_dummy_alternative_explanation()))
    inferred_artifact = plugin.build(_context(_dummy_alternative_explanation(), infer_roles=True))

    assert any(record["primary_role"] == "unknown" for record in default_artifact["rule_records"])
    assert all(record["role_source"] != "heuristic" for record in default_artifact["rule_records"])
    semi_record = next(
        record
        for record in inferred_artifact["rule_records"]
        if record["rule"].startswith("semifactual")
    )
    assert semi_record["primary_role"] == "semi"
    assert semi_record["role_source"] == "heuristic"


def test_counterpotential_is_unknown_without_mapping(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _rules()
    rules["primary_role"][0] = "counterpotential"

    artifact = plugin.build(_context(_dummy_alternative_explanation(rules=rules)))
    mapped = plugin.build(
        _context(
            _dummy_alternative_explanation(rules=rules),
            role_mapping={"counterpotential": "counter"},
        )
    )

    assert artifact["rule_records"][0]["primary_role"] == "unknown"
    assert mapped["rule_records"][0]["primary_role"] == "counter"


def test_renderer_has_no_quality_or_conjunction_panel_by_default(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation())

    result = plugin.render(plugin.build(context), context=context)

    assert result.figure.layout["rows"] == 1
    assert result.figure.layout["subplot_titles"] == ["Primary role and quality-flag combinations"]
    assert all(trace.kwargs["meta"]["panel"] == "role_quality" for trace in result.figure.traces)
    assert not [
        trace for trace in result.figure.traces if trace.kwargs["name"] in {"ensured", "pareto"}
    ]


def test_include_conjunctions_renders_panel_and_counts_sizes(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), include_conjunctions=True)

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)
    feat0 = next(
        summary for summary in artifact["feature_summaries"] if summary["feature_name"] == "feat0"
    )

    assert result.figure.layout["rows"] == 2
    assert "Conjunction involvement" in result.figure.layout["subplot_titles"]
    assert feat0["conjunction_counts"]["size_1"] == 2
    assert feat0["conjunction_counts"]["size_2"] == 1
    assert feat0["conjunction_counts"]["total"] == 3
    feat1 = next(
        summary for summary in artifact["feature_summaries"] if summary["feature_name"] == "feat1"
    )
    assert feat1["conjunction_counts"]["size_1"] == 1
    assert feat1["conjunction_counts"]["size_2"] == 0
    assert feat1["conjunction_counts"]["total"] == 1
    assert [
        trace for trace in result.figure.traces if trace.kwargs["meta"]["panel"] == "conjunctions"
    ]


def test_filter_sort_and_share_hover(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _dummy_alternative_explanation(),
        filter_top_features=1,
        sort_by="ensured",
        normalize="share",
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert len(artifact["feature_summaries"]) == 1
    assert artifact["feature_summaries"][0]["feature_name"] == "feat0"
    assert any(
        "count:" in hover for trace in result.figure.traces for hover in trace.kwargs["hovertext"]
    )
    assert any(
        "bar value: share" in hover
        for trace in result.figure.traces
        for hover in trace.kwargs["hovertext"]
    )


def test_html_export_and_no_normal_fallback_warning(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), path=str(tmp_path / "summary"))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(plugin.build(context), context=context)

    assert result.saved_paths[0].endswith("summary.html")
    assert Path(result.saved_paths[0]).exists()
    assert result.figure is result.extras["figure"]
    assert not caught
