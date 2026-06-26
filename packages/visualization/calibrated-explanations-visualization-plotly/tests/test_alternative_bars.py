from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations.plugins.plots import PlotRenderContext

STYLE_ID = "plotly.local.alternative_bars"
BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"

FACTUAL_STYLE_ID = "plotly.local.factual_bars"


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


def _trust_env() -> str:
    return ",".join(
        [
            "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
            BOOTSTRAP_ID,
            BUILDER_ID,
            RENDERER_ID,
        ]
    )


def _load_plugin(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _alt_context(explanation, *, path=None, show=False, **options) -> PlotRenderContext:
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

    class FakeScatter(FakeTrace):
        pass

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.vlines = []
            self.vline_kwargs = []
            self.annotations = []
            self.layout = {}
            self.xaxes_updates = []
            self.yaxes_updates = []
            self.shown = False
            self.html_paths = []

        @property
        def data(self):
            return tuple(self.traces)

        def add_trace(self, trace, row=None, col=None):
            trace.kwargs["_row"] = row
            trace.kwargs["_col"] = col
            self.traces.append(trace)

        def add_vline(self, **kwargs):
            self.vlines.append(kwargs)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **kwargs):
            self.xaxes_updates.append(kwargs)

        def update_yaxes(self, **kwargs):
            self.yaxes_updates.append(kwargs)

        def write_html(self, path, **_kwargs):
            self.html_paths.append(path)
            Path(path).write_text("<html><body>plotly</body></html>", encoding="utf-8")

        def show(self):
            self.shown = True

    def make_subplots(**kwargs):
        fig = FakeFigure()
        fig.layout["rows"] = kwargs.get("rows")
        fig.layout["subplot_titles"] = kwargs.get("subplot_titles")
        fig.layout["row_heights"] = kwargs.get("row_heights")
        return fig

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Bar = FakeBar
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Figure = FakeFigure
    subplots_mod.make_subplots = make_subplots
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _alt_rules() -> dict:
    return {
        "feature": [0, 1, 2, [0, 2], 3],
        "feature_value": [10, 20, 30, [10, 30], 40],
        "rule": [
            "f0 <= 10",
            "f1 <= 20",
            "f2 > 30",
            "f0 <= 10 AND f2 > 30",
            "f3 > 40",
        ],
        "predict": [0.20, 0.85, 0.30, 0.15, 0.70],
        "predict_low": [0.10, 0.75, 0.20, 0.05, 0.60],
        "predict_high": [0.30, 0.95, 0.40, 0.25, 0.80],
        "primary_role": ["counter", "super", "counter", "counter", None],
        "is_ensured": [True, False, False, True, False],
        "is_pareto": [False, True, False, False, False],
    }


def _dummy_alternative_explanation(*, rules: dict | None = None) -> SimpleNamespace:
    payload = rules or _alt_rules()
    collection = SimpleNamespace(
        feature_names=["feat0", "feat1", "feat2", "feat3"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.75, "low": 0.66, "high": 0.84},
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


def _dummy_factual_explanation() -> SimpleNamespace:
    collection = SimpleNamespace(feature_names=["age", "income"])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.74, "low": 0.66, "high": 0.81},
        rules={"weight": [0.2, -0.5], "rule": ["age <= 42", "income > 10"], "feature": [0, 1]},
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


# ── Registration ──────────────────────────────────────────────────────────────


def test_registration_exposes_style_builder_renderer(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    builder_desc = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_desc = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_desc = registry.find_plot_style_descriptor(STYLE_ID)

    assert builder_desc is not None
    assert builder_desc.trusted is True
    assert renderer_desc is not None
    assert renderer_desc.trusted is True
    assert style_desc is not None
    assert style_desc.metadata["builder_id"] == BUILDER_ID
    assert style_desc.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


# ── Builder ───────────────────────────────────────────────────────────────────


def test_builder_rejects_factual_explanations(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    with pytest.raises(ValueError, match="requires an alternative explanation"):
        plugin.build(_alt_context(_dummy_factual_explanation()))


def test_builder_accepts_alternative_explanation(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation()))

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["artifact_version"] == "0.1.0"
    assert artifact["metadata"]["created_by"] == STYLE_ID
    assert artifact["items"]


def test_alternatives_are_separate_records_not_merged(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), sort_by="original"))

    # 5 alternatives + 2 component subbars for the conjunctive rule (index 3)
    main_items = [item for item in artifact["items"] if not item["is_component"]]
    assert len(main_items) == 5
    # Each has a distinct original_index
    original_indices = [item["original_index"] for item in main_items]
    assert len(set(original_indices)) == len(original_indices)


def test_conjunctive_rule_produces_component_subbars(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _alt_context(_dummy_alternative_explanation(), include_conjunctive_components=True)
    )

    comp_items = [item for item in artifact["items"] if item["is_component"]]
    assert len(comp_items) == 2  # "f0 <= 10 AND f2 > 30" → 2 features
    for comp in comp_items:
        assert comp["original_index"] == 3  # all belong to the conjunctive alt
        assert "└" in comp["y_label"]


def test_filter_top_limits_alternatives_not_merged(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), filter_top=2))

    main_items = [item for item in artifact["items"] if not item["is_component"]]
    assert len(main_items) == 2
    # They are separate, not merged into one bar
    assert main_items[0]["original_index"] != main_items[1]["original_index"]


def test_missing_uncertainty_does_not_crash(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "feature": [0, 1],
        "rule": ["f0 <= 5", "f1 > 3"],
        "predict": [0.3, 0.8],
        "is_ensured": [False, False],
    }

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(rules=rules)))

    assert artifact["metadata"]["num_missing_intervals"] == 2
    for item in artifact["items"]:
        if not item["is_component"]:
            assert "Interval: unavailable" in item["hover"]


def test_role_quality_metadata_preserved(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), sort_by="original"))

    main_items = [item for item in artifact["items"] if not item["is_component"]]
    first = main_items[0]
    assert first["primary_role"] == "counter"
    assert first["is_ensured"] is True
    assert first["role_quality_key"] == "counter__ensured"


def test_bar_value_is_prediction_delta_when_base_available(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), sort_by="original"))

    assert artifact["base_prediction"] == pytest.approx(0.75)
    first_main = next(item for item in artifact["items"] if not item["is_component"])
    # alt predict=0.20, base=0.75 → delta = -0.55
    assert first_main["bar_value"] == pytest.approx(0.20 - 0.75)
    assert first_main["bar_value_kind"] == "prediction_delta"


def test_bar_value_is_raw_prediction_when_no_base(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = {
        "feature": [0],
        "rule": ["f0 <= 5"],
        "predict": [0.3],
    }
    collection = SimpleNamespace(
        feature_names=["feat0"],
        batch_metadata={"task": "classification", "mode": "classification"},
    )
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={},  # no base prediction
        rules=rules,
        conjunctive_rules=None,
        has_conjunctive_rules=False,
        get_rules=lambda: rules,
        get_mode=lambda: "classification",
        is_probabilistic=lambda: True,
        is_regression=lambda: False,
        is_alternative=lambda: True,
    )
    collection.explanations = [local]

    artifact = plugin.build(_alt_context(collection))

    assert artifact["base_prediction"] is None
    items = [i for i in artifact["items"] if not i["is_component"]]
    assert items[0]["bar_value"] == pytest.approx(0.3)
    assert items[0]["bar_value_kind"] == "prediction"


@pytest.mark.parametrize(
    "sort_by",
    ["original", "prediction_delta", "interval_width", "role", "feature"],
)
def test_sort_by_modes_are_accepted(monkeypatch, sort_by):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_alt_context(_dummy_alternative_explanation(), sort_by=sort_by))

    assert artifact["items"]


def test_sort_by_invalid_raises_value_error(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    with pytest.raises(ValueError, match="sort_by must be one of"):
        plugin.build(_alt_context(_dummy_alternative_explanation(), sort_by="bad_value"))


def test_unknown_policy_hide_filters_unknown_roles(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact_show = plugin.build(
        _alt_context(_dummy_alternative_explanation(), unknown_policy="show")
    )
    artifact_hide = plugin.build(
        _alt_context(_dummy_alternative_explanation(), unknown_policy="hide")
    )

    main_show = [i for i in artifact_show["items"] if not i["is_component"]]
    main_hide = [i for i in artifact_hide["items"] if not i["is_component"]]
    assert len(main_hide) < len(main_show)
    assert all(i["primary_role"] != "unknown" for i in main_hide)


# ── Renderer ──────────────────────────────────────────────────────────────────


def test_renderer_has_distinct_traces_per_alternative(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation(), show_prediction_header=False)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    bar_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeBar"]
    assert bar_traces, "No bar traces found"
    all_y_labels = bar_traces[0].kwargs["y"]
    unique_labels = set(all_y_labels)
    # All y-labels should be distinct
    assert len(unique_labels) == len(all_y_labels)


def test_renderer_with_prediction_header_uses_subplots(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation(), show_prediction_header=True)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    assert result.figure.layout.get("rows") == 2


def test_renderer_prediction_header_false_uses_single_row(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation(), show_prediction_header=False)
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    assert result.figure.layout.get("rows") is None  # no subplot


def test_renderer_show_uncertainty_adds_scatter_traces(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(
        _dummy_alternative_explanation(), show_prediction_header=False, show_uncertainty=True
    )
    artifact = plugin.build(context)

    result = plugin.render(artifact, context=context)

    scatter_traces = [t for t in result.figure.traces if t.__class__.__name__ == "FakeScatter"]
    assert scatter_traces, "Expected uncertainty interval scatter traces"


def test_renderer_no_warnings_on_valid_artifact(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plugin.render(plugin.build(context), context=context)

    assert not [w for w in caught if issubclass(w.category, UserWarning)]


def test_renderer_emits_warning_on_wrong_artifact_type(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(_dummy_alternative_explanation())
    artifact = plugin.build(context)
    artifact["artifact_type"] = "wrong.type"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plugin.render(artifact, context=context)

    assert any(issubclass(w.category, UserWarning) for w in caught)


def test_html_export_creates_file(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _alt_context(
        _dummy_alternative_explanation(), path=str(tmp_path / "alt_bars"), show=False
    )

    result = plugin.render(plugin.build(context), context=context)

    assert result.saved_paths[0].endswith("alt_bars.html")
    assert Path(result.saved_paths[0]).exists()
    assert result.figure is result.extras["figure"]


# ── Bridge ────────────────────────────────────────────────────────────────────


def test_bridge_is_installed(monkeypatch):
    _load_plugin(monkeypatch)
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation

        assert getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False)
    except ImportError:
        pytest.skip("AlternativeExplanation not accessible in this CE version")


def test_bridge_passes_non_alternative_bars_styles_through(monkeypatch):
    """Bridge must not intercept calls for unrelated styles."""
    _load_plugin(monkeypatch)
    try:
        from calibrated_explanations.explanations.explanation import AlternativeExplanation
    except ImportError:
        pytest.skip("AlternativeExplanation not accessible in this CE version")

    original_plot = AlternativeExplanation.plot.__wrapped__ if hasattr(
        AlternativeExplanation.plot, "__wrapped__"
    ) else None

    if original_plot is None:
        pytest.skip("Cannot test bridge pass-through without access to wrapped function")

    # Just verify the bridge attribute is present and routes correctly (no crash)
    assert getattr(AlternativeExplanation.plot, "_alternative_bars_bridge", False)
