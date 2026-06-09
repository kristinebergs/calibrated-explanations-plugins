from __future__ import annotations

import importlib
import sys
import types
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import WrapCalibratedExplainer
from calibrated_explanations.plugins.plots import PlotRenderContext
from sklearn.datasets import make_classification, make_regression
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split

STYLE_ID = "plotly.local.ensured"
ALIAS_STYLE_ID = "plotly.local.ensured_triangular"
BUILDER_ID = "official.visualization.plotly.local.ensured.builder"
RENDERER_ID = "official.visualization.plotly.local.ensured.renderer"
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


def _context(explanation, *, style=STYLE_ID, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=style,
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
            self.click_handler = None

        def on_click(self, callback):
            self.click_handler = callback

    class FakeScatter(FakeTrace):
        pass

    class FakeTable(FakeTrace):
        pass

    class FakeFigure:
        def __init__(self):
            self.traces = []
            self.annotations = []
            self.layout = {}
            self.shown = False
            self.html_paths = []
            self.html_write_kwargs = []
            self.html_fragments = []

        @property
        def data(self):
            return tuple(self.traces)

        def add_trace(self, trace, row=None, col=None):
            if row is not None:
                trace.kwargs["row"] = row
            if col is not None:
                trace.kwargs["col"] = col
            self.traces.append(trace)

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def write_html(self, path, **kwargs):
            self.html_paths.append(path)
            self.html_write_kwargs.append(kwargs)

        def to_html(self, **kwargs):
            self.html_fragments.append(kwargs)
            div_id = kwargs.get("div_id", "plotly-div")
            return f'<div id="{div_id}" class="plotly-graph-div"></div>'

        def show(self):
            self.shown = True

    class FakeFigureWidget(FakeFigure):
        def __init__(self, figure=None):
            super().__init__()
            if figure is None:
                return
            self.traces = list(getattr(figure, "traces", []))
            self.annotations = list(getattr(figure, "annotations", []))
            self.layout = dict(getattr(figure, "layout", {}))
            self.shown = getattr(figure, "shown", False)
            self.html_paths = list(getattr(figure, "html_paths", []))
            self.html_write_kwargs = list(getattr(figure, "html_write_kwargs", []))

    def make_subplots(**_kwargs):
        return FakeFigure()

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    subplots_mod = types.ModuleType("plotly.subplots")
    graph_objects_mod.Figure = FakeFigure
    graph_objects_mod.FigureWidget = FakeFigureWidget
    graph_objects_mod.Scatter = FakeScatter
    graph_objects_mod.Table = FakeTable
    subplots_mod.make_subplots = make_subplots
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots_mod)
    return FakeFigure


def _base_alternative_rules() -> dict:
    return {
        "base_predict": [0.72, 0.72, 0.72, 0.72],
        "base_predict_low": [0.64, 0.64, 0.64, 0.64],
        "base_predict_high": [0.80, 0.80, 0.80, 0.80],
        "classes": [1.0, 1.0, 1.0, 1.0],
        "feature": [0, 1, 2, 3],
        "feature_value": [41, 39000, "B", 0.4],
        "is_conjunctive": [False, False, False, True],
        "predict": [0.66, 0.81, 0.49, 0.77],
        "predict_low": [0.58, 0.74, 0.40, 0.72],
        "predict_high": [0.73, 0.88, 0.60, 0.83],
        "rule": ["age <= 40", None, "segment = A", "risk <= 0.5 AND tenure > 2"],
        "sampled_values": [[38, 35], [42000], ["A"], [0.1, 0.2]],
        "value": ["41", "39000", "B", "0.4"],
        "weight": [-0.06, 0.09, -0.23, 0.05],
        "weight_low": [-0.14, 0.02, -0.32, 0.00],
        "weight_high": [0.01, 0.16, -0.12, 0.11],
    }


def _rules_with_feature_count(feature_count: int) -> dict:
    return {
        "base_predict": [0.72] * feature_count,
        "base_predict_low": [0.64] * feature_count,
        "base_predict_high": [0.80] * feature_count,
        "classes": [1.0] * feature_count,
        "feature": list(range(feature_count)),
        "feature_value": [float(index) for index in range(feature_count)],
        "is_conjunctive": [False] * feature_count,
        "predict": [0.55 + 0.01 * index for index in range(feature_count)],
        "predict_low": [0.45 + 0.01 * index for index in range(feature_count)],
        "predict_high": [0.65 + 0.01 * index for index in range(feature_count)],
        "rule": [f"feature_{index} <= {index}" for index in range(feature_count)],
        "sampled_values": [[float(index)] for index in range(feature_count)],
        "value": [str(index) for index in range(feature_count)],
        "weight": [0.01 * index for index in range(feature_count)],
        "weight_low": [0.01 * index - 0.02 for index in range(feature_count)],
        "weight_high": [0.01 * index + 0.02 for index in range(feature_count)],
    }


def _dummy_alternative_explanation(
    *, rules: dict | None = None, regression: bool = False
) -> SimpleNamespace:
    collection = SimpleNamespace(
        feature_names=["age", "income", "segment", "risk"],
        batch_metadata={
            "task": "regression" if regression else "classification",
            "mode": "regression" if regression else "classification",
        },
    )

    def rank_features(*, width, num_to_show, **_kwargs):
        return sorted(range(len(width)), key=lambda index: (float(width[index]), index))[
            :num_to_show
        ]

    payload = rules or _base_alternative_rules()
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={
            "predict": 0.72 if not regression else 12.0,
            "low": 0.64 if not regression else 10.0,
            "high": 0.80 if not regression else 13.0,
            "classes": 1.0,
        },
        rules=payload,
        conjunctive_rules=None,
        has_conjunctive_rules=False,
        y_minmax=(0.0, 1.0) if not regression else (0.0, 20.0),
        get_mode=lambda: "regression" if regression else "classification",
        is_probabilistic=lambda: not regression,
        is_regression=lambda: regression,
        is_thresholded=lambda: False,
        is_alternative=lambda: True,
        rank_features=rank_features,
        get_rules=lambda: payload,
    )
    collection.explanations = [local]
    return collection


def _subset_rules(rules: dict, indexes: list[int]) -> dict:
    subset = {}
    for key, values in rules.items():
        if isinstance(values, list) and len(values) == len(rules["rule"]):
            subset[key] = [values[index] for index in indexes]
        else:
            subset[key] = values
    return subset


def _dummy_conjunctive_alternative_explanation() -> SimpleNamespace:
    rules = _base_alternative_rules()
    conjunctive_rules = _subset_rules(rules, [0, 1, 2, 3])
    conjunctive_rules["feature"][3] = [0, 3]
    conjunctive_rules["rule"][3] = "age <= 40 AND risk <= 0.5"
    conjunctive_rules["is_conjunctive"][3] = True
    explanation = _dummy_alternative_explanation(rules=rules)
    local = explanation.explanations[0]
    local.conjunctive_rules = conjunctive_rules
    local.has_conjunctive_rules = True
    local.get_rules = lambda: conjunctive_rules
    return explanation


def test_canonical_registration_alias_and_trusted_resolution(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    builder_descriptor = registry.find_plot_builder_descriptor(BUILDER_ID)
    renderer_descriptor = registry.find_plot_renderer_descriptor(RENDERER_ID)
    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    alias_descriptor = registry.find_plot_style_descriptor(ALIAS_STYLE_ID)
    assert builder_descriptor is not None
    assert builder_descriptor.trusted is True
    assert renderer_descriptor is not None
    assert renderer_descriptor.trusted is True
    assert style_descriptor is not None
    assert style_descriptor.metadata["builder_id"] == BUILDER_ID
    assert style_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert alias_descriptor is not None
    assert alias_descriptor.metadata["builder_id"] == BUILDER_ID
    assert alias_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


def test_deprecated_alias_emits_warning(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(ALIAS_STYLE_ID)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        artifact = plugin.build(
            _context(_dummy_alternative_explanation(), style=ALIAS_STYLE_ID, filter_top=2)
        )

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["metadata"]["deprecated_alias_used"] is True
    assert any("deprecated" in str(warning.message).lower() for warning in caught)


def test_builder_enriches_artifact_capabilities_and_options(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _dummy_alternative_explanation(),
            filter_top=3,
            feature_checklist=True,
            side_panel=True,
        )
    )

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["artifact_version"] == "0.2.0"
    assert artifact["base_plotspec_kind"] == "triangular"
    assert artifact["original"]["label"] == "Original Prediction"
    assert artifact["options_used"]["feature_checklist"] is True
    assert artifact["options_used"]["side_panel"] is True
    assert artifact["interaction_capabilities"] == {
        "hover": True,
        "html_export": True,
        "filter_top": True,
        "arrows": True,
        "feature_checklist": True,
        "check_all": True,
        "uncheck_all": True,
        "side_panel": True,
        "click_detail_panel": True,
        "marker_uncertainty_encoding": False,
    }
    assert artifact["metadata"]["shown_rule_count"] == 3
    assert artifact["metadata"]["missing_rule_metadata_count"] == 1
    assert artifact["metadata"]["feature_count"] >= 1
    assert all(point["hover"] for point in artifact["rule_points"])


def test_compact_rule_hover_shows_only_requested_fields(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(_context(_dummy_alternative_explanation(), filter_top=1))
    hover_text = artifact["rule_points"][0]["hover"]

    assert "Rule:" in hover_text
    assert "Prediction:" in hover_text
    assert "Uncertainty:" in hover_text
    assert "Interval:" in hover_text
    assert "Conjunction size:" in hover_text
    assert "Feature:" not in hover_text
    assert "Delta prediction:" not in hover_text
    assert "Rank:" not in hover_text


def test_role_fallback_unknown_when_metadata_unavailable(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["predict"] = [0.74, 0.73, 0.71, 0.70]
    rules["predict_low"] = [0.60, 0.62, 0.60, 0.60]
    rules["predict_high"] = [0.90, 0.91, 0.92, 0.93]

    artifact = plugin.build(_context(_dummy_alternative_explanation(rules=rules), filter_top=4))

    assert any(point["explanation_role"] == "unknown" for point in artifact["rule_points"])
    assert artifact["metadata"]["missing_role_metadata_count"] >= 1


def test_role_priority_prefers_ensured_then_pareto(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["is_ensured"] = [True, False, False, False]
    rules["is_pareto"] = [True, True, False, False]
    rules["is_counterfactual"] = [True, True, True, False]

    artifact = plugin.build(_context(_dummy_alternative_explanation(rules=rules), filter_top=3))

    ensured_point = next(point for point in artifact["rule_points"] if point["is_ensured"])
    pareto_only_point = next(
        point for point in artifact["rule_points"] if point["is_pareto"] and not point["is_ensured"]
    )

    assert ensured_point["explanation_role"] == "ensured"
    assert ensured_point["role_source"] == "rule_metadata"
    assert pareto_only_point["explanation_role"] == "pareto"


def test_role_membership_uses_alternative_explanation_filters(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["is_ensured"] = [False, False, False, False]
    rules["is_pareto"] = [False, False, False, False]
    rules["is_counterfactual"] = [False, False, False, False]
    rules["is_semifactual"] = [False, False, False, False]
    rules["is_counterpotential"] = [False, False, False, False]
    explanation = _dummy_alternative_explanation(rules=rules)
    local = explanation.explanations[0]
    calls = []

    def filtered(indexes):
        return SimpleNamespace(get_rules=lambda: _subset_rules(rules, indexes))

    def pareto(*, include_potential=True, copy=True, pareto_cost="uncertainty_width"):
        calls.append(("pareto", include_potential, copy, pareto_cost))
        return filtered([1])

    def semi(*, only_ensured=False, include_potential=True, copy=True):
        calls.append(("semi", only_ensured, include_potential, copy))
        return filtered([0])

    def super_(*, only_ensured=False, include_potential=True, copy=True):
        calls.append(("super", only_ensured, include_potential, copy))
        return filtered([3])

    def counter(*, only_ensured=False, include_potential=True, copy=True):
        calls.append(("counter", only_ensured, include_potential, copy))
        return filtered([2])

    local.pareto = pareto
    local.semi = semi
    local.super = super_
    local.counter = counter

    artifact = plugin.build(_context(explanation, filter_top=4, pareto_cost="rule_size"))
    points = {point["index"]: point for point in artifact["rule_points"]}

    assert points[1]["is_pareto"] is True
    assert points[0]["is_semifactual"] is True
    assert points[3]["is_counterpotential"] is True
    assert points[2]["is_counterfactual"] is True
    assert points[1]["role_source"] == "ce_metadata"
    assert ("pareto", True, True, "rule_size") in calls
    assert ("semi", False, True, True) in calls
    assert ("super", False, True, True) in calls
    assert ("counter", False, True, True) in calls


def test_role_membership_maps_conjunctive_filtered_rules(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    explanation = _dummy_conjunctive_alternative_explanation()
    local = explanation.explanations[0]
    rules = local.conjunctive_rules

    def filtered(indexes):
        filtered_rules = _subset_rules(rules, indexes)
        filtered_rules["feature"] = [
            list(reversed(feature)) if isinstance(feature, list) else feature
            for feature in filtered_rules["feature"]
        ]
        filtered_rules["rule"] = [
            str(rule).replace(" AND ", " & ") for rule in filtered_rules["rule"]
        ]
        return SimpleNamespace(
            has_conjunctive_rules=True,
            conjunctive_rules=MappingProxyType(filtered_rules),
            get_rules=lambda: filtered_rules,
        )

    local.pareto = lambda **_kwargs: filtered([3])
    local.semi = lambda **_kwargs: filtered([0])
    local.super = lambda **_kwargs: filtered([1])
    local.counter = lambda **_kwargs: filtered([2])

    artifact = plugin.build(_context(explanation, filter_top=4))
    points = {point["index"]: point for point in artifact["rule_points"]}

    assert points[3]["is_conjunctive"] is True
    assert points[3]["conjunction_size"] == 2
    assert points[3]["is_pareto"] is True
    assert points[0]["is_semifactual"] is True
    assert points[1]["is_counterpotential"] is True
    assert points[2]["is_counterfactual"] is True
    assert points[3]["role_source"] == "ce_metadata"


def test_renderer_returns_plotly_figure_and_default_arrows(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=3)
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    original_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "original"
    ]
    rule_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
    ]
    assert result.figure is result.extras["figure"]
    assert len(original_traces) == 1
    assert (
        sum(len(trace.kwargs["x"]) for trace in rule_traces)
        == artifact["metadata"]["shown_rule_count"]
    )
    assert len(result.figure.annotations) == artifact["metadata"]["shown_rule_count"]
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


def test_side_panel_show_uses_html_shell_display_instead_of_show(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    displayed = []

    ipython_mod = types.ModuleType("IPython")
    ipython_display_mod = types.ModuleType("IPython.display")

    class FakeHTML:
        def __init__(self, data):
            self.data = data

    def fake_display(value):
        displayed.append(value)

    ipython_display_mod.HTML = FakeHTML
    ipython_display_mod.display = fake_display
    monkeypatch.setitem(sys.modules, "IPython", ipython_mod)
    monkeypatch.setitem(sys.modules, "IPython.display", ipython_display_mod)

    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=3, side_panel=True, show=True)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert len(displayed) == 1
    assert isinstance(displayed[0], FakeHTML)
    assert "Rule details" in displayed[0].data
    assert result.extras["html"] == displayed[0].data
    assert result.figure.shown is False


def test_show_arrows_false_suppresses_arrows(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), show_arrows=False, filter_top=2)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    arrow_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "arrows"
    ]
    assert result.figure.annotations == []
    assert arrow_traces == []


def test_filter_top_limits_rendered_rule_points_and_arrows(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), max_points=2, sort_by="delta_prediction")
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)
    rule_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
    ]

    assert artifact["options_used"]["filter_top"] == 2
    assert artifact["metadata"]["shown_rule_count"] == 2
    assert len(artifact["arrows"]) == 2
    assert sum(len(trace.kwargs["x"]) for trace in rule_traces) == 2
    assert len(result.figure.annotations) == 2


def test_feature_checklist_false_has_no_controls(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    result = plugin.render(
        plugin.build(_context(_dummy_alternative_explanation(), filter_top=3)),
        context=_context(_dummy_alternative_explanation(), filter_top=3),
    )

    assert "updatemenus" not in result.figure.layout
    assert result.extras["html"] is None


def test_feature_checklist_true_renders_searchable_shell_and_trace_registry(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=3, feature_checklist=True)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    feature_registry = result.figure.layout["meta"]["feature_control_registry"]
    assert feature_registry
    assert "Filter by searched feature (regex)" in result.extras["html"]
    assert "new RegExp(rawValue, 'i')" in result.extras["html"]
    assert "Invalid regex" in result.extras["html"]
    assert "applySelection();" in result.extras["html"]
    assert 'data-feature-action="all"' in result.extras["html"]
    assert 'data-feature-action="ensured"' in result.extras["html"]
    assert 'data-feature-action="pareto"' in result.extras["html"]
    assert 'data-role-filter="counter" checked' in result.extras["html"]
    assert 'data-role-filter="semi" checked' in result.extras["html"]
    assert 'data-role-filter="super" checked' in result.extras["html"]
    assert "rolePreset = action" in result.extras["html"]
    assert "rolePreset === 'pareto'" in result.extras["html"]
    assert "return true;" in result.extras["html"]
    assert 'data-feature-action="topk"' not in result.extras["html"]
    assert all(item["default_selected"] for item in feature_registry)


def test_feature_checklist_rule_traces_expose_role_filter_metadata(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["is_ensured"] = [True, False, False, False]
    rules["is_pareto"] = [False, True, False, False]
    rules["is_counterfactual"] = [True, False, False, False]
    rules["is_semifactual"] = [False, False, True, False]
    rules["is_counterpotential"] = [False, False, False, True]
    context = _context(
        _dummy_alternative_explanation(rules=rules),
        filter_top=4,
        feature_checklist=True,
    )

    result = plugin.render(plugin.build(context), context=context)

    role_metadata = [
        trace.kwargs.get("meta", {}).get("roles", {})
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
    ]
    assert any(roles.get("ensured") and roles.get("counter") for roles in role_metadata)
    assert any(roles.get("pareto") for roles in role_metadata)
    assert any(roles.get("semi") for roles in role_metadata)
    assert any(roles.get("super") for roles in role_metadata)


def test_feature_checklist_arrow_traces_expose_role_filter_metadata(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["feature"] = [0, 0, 0, 0]
    rules["is_ensured"] = [False, False, False, False]
    rules["is_pareto"] = [True, False, False, False]
    rules["is_counterfactual"] = [False, True, False, False]
    rules["is_semifactual"] = [False, False, True, False]
    rules["is_counterpotential"] = [False, False, False, True]
    context = _context(
        _dummy_alternative_explanation(rules=rules),
        filter_top=4,
        feature_checklist=True,
        side_panel=True,
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    arrow_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "arrows"
    ]
    assert len(arrow_traces) >= 4
    arrow_roles = [trace.kwargs.get("meta", {}).get("roles", {}) for trace in arrow_traces]
    assert any(roles.get("pareto") for roles in arrow_roles)
    assert any(roles.get("counter") for roles in arrow_roles)
    assert any(roles.get("semi") for roles in arrow_roles)
    assert any(roles.get("super") for roles in arrow_roles)
    assert "meta.trace_kind === 'arrows' && !rolesAllowed" in result.extras["html"]


def test_feature_checklist_defaults_to_all_for_large_feature_sets(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _dummy_alternative_explanation(rules=_rules_with_feature_count(10)),
        filter_top=10,
        feature_checklist=True,
    )
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    feature_registry = result.figure.layout["meta"]["feature_control_registry"]
    assert len(feature_registry) == 10
    assert all(item["default_selected"] for item in feature_registry)
    hidden_rule_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
        and trace.kwargs.get("visible") is False
    ]
    assert not hidden_rule_traces


def test_rule_marker_size_corresponds_to_conjunction_size(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=4)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    conjunctive_point = next(point for point in artifact["rule_points"] if point["is_conjunctive"])
    single_point = next(point for point in artifact["rule_points"] if not point["is_conjunctive"])
    assert conjunctive_point["conjunction_size"] == 2
    assert single_point["conjunction_size"] == 1

    rule_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
    ]
    rendered_sizes = [size for trace in rule_traces for size in trace.kwargs["marker"]["size"]]
    assert 9 in rendered_sizes
    assert 14 in rendered_sizes


def test_rule_marker_size_scales_to_capped_max_conjunction_size(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["feature"][3] = [0, 1, 2]
    rules["rule"][3] = "age <= 40 AND income <= 39000 AND segment = A"
    context = _context(_dummy_alternative_explanation(rules=rules), filter_top=4)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    three_part = next(point for point in artifact["rule_points"] if point["conjunction_size"] == 3)
    assert three_part["is_conjunctive"] is True

    rule_traces = [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "rule-points"
    ]
    rendered_sizes = [size for trace in rule_traces for size in trace.kwargs["marker"]["size"]]
    assert max(rendered_sizes) == 14
    assert min(rendered_sizes) == 9


def test_side_panel_false_has_no_table(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    result = plugin.render(
        plugin.build(_context(_dummy_alternative_explanation(), filter_top=3)),
        context=_context(_dummy_alternative_explanation(), filter_top=3),
    )

    assert not [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "side-panel"
    ]
    assert result.extras["html"] is None


def test_side_panel_true_registers_text_payload_and_shell(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), filter_top=3, side_panel=True)
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert not [
        trace
        for trace in result.figure.traces
        if trace.kwargs.get("meta", {}).get("trace_kind") == "side-panel"
    ]
    assert result.figure.layout["meta"]["side_panel_trace_index"] is None
    registry_rows = result.figure.layout["meta"]["side_panel_registry"]
    assert registry_rows
    first_rule = artifact["rule_points"][0]
    detail_rows = registry_rows[first_rule["id"]]
    assert detail_rows["title"] == first_rule["feature_name"]
    assert "ce-ensured-detail-row" in detail_rows["body_html"]
    assert "ce-ensured-detail-label" in detail_rows["body_html"]
    assert "Rule" in detail_rows["body_html"]
    assert "Interval" in detail_rows["body_html"]
    assert "Roles" in detail_rows["body_html"]
    assert "Current value" not in detail_rows["body_html"]
    assert "True value" not in detail_rows["body_html"]
    assert "Alternative" not in detail_rows["body_html"]
    assert "Role source" not in detail_rows["body_html"]
    assert "Role</div>" not in detail_rows["body_html"]
    assert "Metadata" not in detail_rows["body_html"]
    assert "Rule details" in result.extras["html"]


def test_side_panel_roles_include_all_active_flags(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    rules = _base_alternative_rules()
    rules["is_ensured"] = [True, True, True, True]
    rules["is_pareto"] = [True, True, True, True]
    rules["is_counterfactual"] = [True, True, True, True]
    artifact = plugin.build(
        _context(_dummy_alternative_explanation(rules=rules), filter_top=4, side_panel=True)
    )
    result = plugin.render(
        artifact,
        context=_context(
            _dummy_alternative_explanation(rules=rules), filter_top=4, side_panel=True
        ),
    )

    first_rule = artifact["rule_points"][0]
    detail_rows = result.figure.layout["meta"]["side_panel_registry"][first_rule["id"]]
    assert "Ensured, Pareto, Counter" in detail_rows["body_html"]


def test_sort_by_is_deterministic(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_dummy_alternative_explanation(), sort_by="delta_prediction", filter_top=3)

    artifact_one = plugin.build(context)
    artifact_two = plugin.build(context)

    assert [point["id"] for point in artifact_one["rule_points"]] == [
        point["id"] for point in artifact_two["rule_points"]
    ]


def test_html_export_when_context_path_is_supplied(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _dummy_alternative_explanation(),
        path=str(tmp_path / "ensured_export"),
        filter_top=2,
        feature_checklist=True,
        side_panel=True,
    )
    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert result.saved_paths[0].endswith("ensured_export.html")
    saved_html = Path(result.saved_paths[0]).read_text(encoding="utf-8")
    assert "Filter by searched feature (regex)" in saved_html
    assert "Rule details" in saved_html
    assert "plotly-graph-div" in saved_html


def test_smoke_path_with_wrap_calibrated_explainer_classification(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)

    features, labels = make_classification(
        n_samples=180,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_proper, x_holdout, y_proper, y_holdout = train_test_split(
        features,
        labels,
        test_size=0.4,
        random_state=0,
        stratify=labels,
    )
    x_cal, x_query, y_cal, _ = train_test_split(
        x_holdout,
        y_holdout,
        test_size=0.5,
        random_state=0,
        stratify=y_holdout,
    )

    model = LogisticRegression(random_state=0, solver="liblinear")
    explainer = WrapCalibratedExplainer(model)
    explainer.fit(x_proper, y_proper)
    explainer.calibrate(x_cal, y_cal)
    alternatives = explainer.explore_alternatives(x_query[:1])

    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(alternatives, filter_top=5)
    result = plugin.render(plugin.build(context), context=context)

    assert result is not None
    assert result.artifact["artifact_type"] == STYLE_ID
    assert result.figure is result.extras["figure"]
    assert result.artifact["metadata"]["shown_rule_count"] >= 1


def test_smoke_path_with_wrap_calibrated_explainer_regression(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)

    features, target = make_regression(n_samples=180, n_features=5, noise=0.1, random_state=0)
    x_proper, x_holdout, y_proper, y_holdout = train_test_split(
        features,
        target,
        test_size=0.4,
        random_state=0,
    )
    x_cal, x_query, y_cal, _ = train_test_split(
        x_holdout,
        y_holdout,
        test_size=0.5,
        random_state=0,
    )

    model = LinearRegression()
    explainer = WrapCalibratedExplainer(model)
    explainer.fit(x_proper, y_proper)
    explainer.calibrate(x_cal, y_cal)
    alternatives = explainer.explore_alternatives(x_query[:1], low_high_percentiles=(10, 90))

    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(alternatives, filter_top=5, side_panel=True)
    result = plugin.render(plugin.build(context), context=context)

    assert result is not None
    assert result.artifact["task"] == "regression"
    assert result.figure is result.extras["figure"]
