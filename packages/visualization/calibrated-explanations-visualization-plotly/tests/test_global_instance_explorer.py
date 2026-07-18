from __future__ import annotations

import importlib
import sys
import types
import warnings
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import WrapCalibratedExplainer
from calibrated_explanations.plugins.plots import PlotRenderContext
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

STYLE_ID = "plotly.global.instance_explorer"
BUILDER_ID = "official.visualization.plotly.global.instance_explorer.builder"
RENDERER_ID = "official.visualization.plotly.global.instance_explorer.renderer"
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
    monkeypatch.setenv("CE_TRUST_PLUGIN", _trust_env())
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _context(explanation, *, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "batch"}),
        style=STYLE_ID,
        intent=MappingProxyType({"type": "global"}),
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
        def __init__(self):
            self.traces = []
            self.layout = {}
            self.shown = False
            self.html_paths = []

        def add_trace(self, trace):
            self.traces.append(trace)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def write_html(self, path):
            self.html_paths.append(path)

        def show(self):
            self.shown = True

    plotly_mod = types.ModuleType("plotly")
    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    graph_objects_mod.Figure = FakeFigure
    graph_objects_mod.Scatter = FakeScatter
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)
    return FakeFigure


def _collection(task: str, predictions: list[dict], *, threshold=None, percentiles=None):
    collection = SimpleNamespace(
        batch_metadata={
            "task": "regression" if task != "classification" else "classification",
            "mode": "regression" if task != "classification" else "classification",
            "y_threshold": threshold,
            "low_high_percentiles": percentiles,
        }
    )
    locals_ = []
    for index, prediction in enumerate(predictions):
        local = SimpleNamespace(
            index=index,
            calibrated_explanations=collection,
            prediction=prediction,
            y_threshold=threshold,
            low_high_percentiles=percentiles,
            get_mode=lambda task=task: "classification"
            if task == "classification"
            else "regression",
            is_thresholded=lambda task=task: task == "probabilistic_regression",
        )
        locals_.append(local)
    collection.explanations = locals_
    return collection


def _classification_payload():
    return _collection(
        "classification",
        [
            {"predict": 0.821, "low": 0.74, "high": 0.89, "classes": 1},
            {"predict": 0.824, "low": 0.75, "high": 0.90, "classes": 1},
            {"predict": 0.41, "low": 0.33, "high": 0.53, "classes": 0},
        ],
    )


def _probabilistic_regression_payload():
    return _collection(
        "probabilistic_regression",
        [
            {"predict": 0.67, "low": 0.55, "high": 0.78, "classes": 1},
            {"predict": 0.671, "low": 0.551, "high": 0.781, "classes": 1},
        ],
        threshold=25.0,
    )


def _conformal_regression_payload():
    return _collection(
        "conformal_regression",
        [
            {"predict": 12.4, "low": 9.8, "high": 15.7, "classes": 1},
            {"predict": 16.2, "low": 11.2, "high": 21.0, "classes": 1},
        ],
        percentiles=(10, 90),
    )


def _global_classification_payload():
    return {
        "proba": [[0.2, 0.8], [0.7, 0.3], [0.1, 0.9], [0.65, 0.35]],
        "low": [[0.1, 0.72], [0.62, 0.22], [0.03, 0.82], [0.55, 0.25]],
        "high": [[0.3, 0.88], [0.78, 0.39], [0.18, 0.94], [0.74, 0.45]],
        "uncertainty": [[0.2, 0.16], [0.16, 0.17], [0.15, 0.12], [0.19, 0.20]],
        "y": [1, 0, 1, 0],
        "is_regularized": True,
        "threshold": None,
        "class_labels": {0: 0, 1: 1},
    }


def _global_regression_payload():
    return {
        "proba": None,
        "predict": [10.0, 12.0, 12.01],
        "low": [8.0, 9.0, 9.01],
        "high": [13.0, 15.0, 15.01],
        "uncertainty": [5.0, 6.0, 6.0],
        "y": [9.5, 11.8, 18.0],
        "is_regularized": False,
        "threshold": None,
    }


def _global_thresholded_regression_payload():
    return {
        "proba": [[0.25, 0.75], [0.8, 0.2], [0.45, 0.55], [0.7, 0.3]],
        "predict": None,
        "low": [[0.15, 0.65], [0.72, 0.11], [0.35, 0.44], [0.62, 0.21]],
        "high": [[0.36, 0.84], [0.90, 0.31], [0.56, 0.67], [0.81, 0.41]],
        "uncertainty": [[0.21, 0.19], [0.18, 0.20], [0.21, 0.23], [0.19, 0.20]],
        "y": [19.0, 25.0, 10.0, 30.0],
        "is_regularized": True,
        "threshold": 20.0,
    }


def _overlapping_class_payload():
    return {
        "proba": [[0.2, 0.8], [0.2, 0.8], [0.2, 0.8], [0.2, 0.8]],
        "low": [[0.1, 0.7], [0.1, 0.7], [0.1, 0.7], [0.1, 0.7]],
        "high": [[0.3, 0.9], [0.3, 0.9], [0.3, 0.9], [0.3, 0.9]],
        "uncertainty": [[0.2, 0.2], [0.2, 0.2], [0.2, 0.2], [0.2, 0.2]],
        "y": [0, 0, 0, 1],
        "is_regularized": True,
        "threshold": None,
        "class_labels": {0: 0, 1: 1},
    }


def test_registration_and_trusted_style_resolution(monkeypatch):
    _load_plugin(monkeypatch)
    registry.mark_plot_builder_trusted(BUILDER_ID)
    registry.mark_plot_renderer_trusted(RENDERER_ID)

    style_descriptor = registry.find_plot_style_descriptor(STYLE_ID)
    assert style_descriptor is not None
    assert style_descriptor.metadata["builder_id"] == BUILDER_ID
    assert style_descriptor.metadata["renderer_id"] == RENDERER_ID
    assert registry.find_plot_plugin_trusted(STYLE_ID) is not None


def test_classification_payload_builds_marker_records(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _classification_payload(),
            task="classification",
            position_precision=2,
            true_labels=[1, 1, 1],
        )
    )

    assert artifact["artifact_type"] == STYLE_ID
    assert artifact["artifact_version"] == "0.1.0"
    assert artifact["axis_metadata"]["task"] == "classification"
    assert artifact["axis_metadata"]["is_probabilistic"] is True
    assert artifact["triangle_reference_metadata"]["enabled"] is True
    assert artifact["aggregation_metadata"]["num_instances"] == 3
    assert artifact["aggregation_metadata"]["num_markers"] == 2
    marker = max(artifact["marker_records"], key=lambda item: item["count"])
    assert marker["count"] == 2
    assert "Instances: 2" in marker["hover"]
    assert "Predicted class:" in marker["hover"]
    assert "Probability interval:" in marker["hover"]


def test_probabilistic_regression_payload_builds_marker_records(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _probabilistic_regression_payload(),
            task="probabilistic_regression",
            position_precision=2,
            target_values=[23.0, 31.0],
        )
    )

    hover = artifact["marker_records"][0]["hover"]
    assert artifact["axis_metadata"]["task"] == "probabilistic_regression"
    assert artifact["triangle_reference_metadata"]["enabled"] is True
    assert "Target event: y <= 25.0" in hover
    assert "Probability interval:" in hover
    assert "Observed event count: 1 / 2" in hover


def test_conformal_regression_payload_builds_marker_records(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(
            _conformal_regression_payload(),
            task="conformal_regression",
            target_values=[12.0, 30.0],
        )
    )

    hover = artifact["marker_records"][0]["hover"]
    assert artifact["axis_metadata"]["task"] == "conformal_regression"
    assert artifact["axis_metadata"]["is_probabilistic"] is False
    assert artifact["triangle_reference_metadata"]["enabled"] is False
    assert "Point prediction / median:" in hover
    assert "Percentiles: 10 / 90" in hover
    assert "Confidence: 80%" in hover
    assert "Prediction interval:" in hover


def test_aggregation_by_rounded_position_and_precision(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    coarse = plugin.build(
        _context(_classification_payload(), task="classification", position_precision=2)
    )
    fine = plugin.build(
        _context(_classification_payload(), task="classification", position_precision=3)
    )

    assert coarse["aggregation_metadata"]["num_markers"] == 2
    assert fine["aggregation_metadata"]["num_markers"] == 3


def test_marker_size_increases_monotonically_with_count(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    payload = _collection(
        "classification",
        [
            {"predict": 0.821, "low": 0.74, "high": 0.89, "classes": 1},
            {"predict": 0.824, "low": 0.75, "high": 0.90, "classes": 1},
            {"predict": 0.822, "low": 0.76, "high": 0.91, "classes": 1},
            {"predict": 0.51, "low": 0.45, "high": 0.59, "classes": 1},
        ],
    )

    artifact = plugin.build(_context(payload, task="classification", position_precision=2))
    sizes = {marker["count"]: marker["marker_size"] for marker in artifact["marker_records"]}
    assert sizes[3] > sizes[1]


def test_aggregate_positions_false_produces_one_marker_per_instance(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    artifact = plugin.build(
        _context(_classification_payload(), task="classification", aggregate_positions=False)
    )

    assert artifact["aggregation_metadata"]["num_markers"] == 3
    assert all(marker["count"] == 1 for marker in artifact["marker_records"])


def test_bin_aggregation_is_deterministic(monkeypatch):
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)

    first = plugin.build(
        _context(
            _classification_payload(),
            task="classification",
            aggregation_strategy="bin",
            position_precision=1,
        )
    )
    second = plugin.build(
        _context(
            _classification_payload(),
            task="classification",
            aggregation_strategy="bin",
            position_precision=1,
        )
    )

    assert first["marker_records"] == second["marker_records"]


def test_html_export_and_no_fallback_warnings(monkeypatch, tmp_path):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _classification_payload(),
        task="classification",
        position_precision=2,
        path=tmp_path / "instance_explorer.html",
    )
    artifact = plugin.build(context)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = plugin.render(artifact, context=context)

    assert result.figure is result.extras["figure"]
    assert result.saved_paths == (str(tmp_path / "instance_explorer.html"),)
    assert result.figure.html_paths == [str(tmp_path / "instance_explorer.html")]
    marker_trace = result.figure.traces[-1]
    assert marker_trace.kwargs["hovertemplate"] == "%{text}<extra></extra>"
    assert [trace.kwargs["meta"]["trace_kind"] for trace in result.figure.traces[:4]] == [
        "triangle-reference",
        "triangle-reference",
        "triangle-reference",
        "triangle-reference",
    ]
    assert not [warning for warning in caught if issubclass(warning.category, UserWarning)]


def test_global_payload_with_targets_uses_target_symbols(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        None,
        payload=_global_classification_payload(),
        position_precision=2,
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert artifact["axis_metadata"]["task"] == "classification"
    assert artifact["axis_metadata"]["x_label"] == "Probability of Y = 1"
    assert artifact["target_metadata"]["target_kind"] == "class"
    assert artifact["target_metadata"]["targets"] == (0, 1)
    legend_traces = result.figure.traces[4:6]
    instance_trace = result.figure.traces[6]
    assert [trace.kwargs["name"] for trace in legend_traces] == ["Y = 0", "Y = 1"]
    assert (
        legend_traces[0].kwargs["marker"]["symbol"] != legend_traces[1].kwargs["marker"]["symbol"]
    )
    assert instance_trace.kwargs["name"] == "instances"
    assert instance_trace.kwargs["showlegend"] is False


def test_global_regression_payload_with_targets_uses_target_color(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        None,
        payload=_global_regression_payload(),
        task="auto",
        position_precision=2,
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert artifact["axis_metadata"]["task"] == "regression"
    assert artifact["axis_metadata"]["is_probabilistic"] is False
    assert artifact["triangle_reference_metadata"]["enabled"] is False
    assert artifact["target_metadata"]["target_kind"] == "continuous"
    assert len(result.figure.traces) == 1
    assert result.figure.traces[0].kwargs["marker"]["colorbar"]["title"] == "Target"


def test_thresholded_regression_targets_become_event_classes(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        None,
        payload=_global_thresholded_regression_payload(),
        task="auto",
        position_precision=2,
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert artifact["axis_metadata"]["task"] == "probabilistic_regression"
    assert artifact["target_metadata"]["target_kind"] == "class"
    assert artifact["target_metadata"]["targets"] == (0, 1)
    assert artifact["target_metadata"]["target_labels"] == {
        "0": "Y >= 20.0",
        "1": "Y < 20.0",
    }
    assert [trace.kwargs["name"] for trace in result.figure.traces[4:6]] == [
        "Y >= 20.0",
        "Y < 20.0",
    ]


def test_overlapping_class_markers_draw_largest_symbol_first(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        None,
        payload=_overlapping_class_payload(),
        position_precision=2,
    )

    artifact = plugin.build(context)
    result = plugin.render(artifact, context=context)

    assert sorted(marker["count"] for marker in artifact["marker_records"]) == [1, 3]
    instance_trace = result.figure.traces[-1]
    assert instance_trace.kwargs["meta"]["draw_order"] == "marker_size_desc"
    assert instance_trace.kwargs["marker"]["size"][0] > instance_trace.kwargs["marker"]["size"][1]
    assert "Instances: 3" in instance_trace.kwargs["text"][0]
    assert "Instances: 1" in instance_trace.kwargs["text"][1]


def test_wrap_explainer_plot_invokes_global_instance_explorer_with_targets(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    import calibrated_explanations.plotting as ce_plotting

    monkeypatch.setattr(ce_plotting, "plt", None, raising=False)
    features, labels = make_classification(
        n_samples=120,
        n_features=5,
        n_informative=3,
        n_redundant=0,
        random_state=23,
    )
    x_proper, x_tmp, y_proper, y_tmp = train_test_split(
        features, labels, test_size=0.4, random_state=23, stratify=labels
    )
    x_cal, x_query, y_cal, y_query = train_test_split(
        x_tmp, y_tmp, test_size=0.5, random_state=23, stratify=y_tmp
    )
    explainer = WrapCalibratedExplainer(RandomForestClassifier(n_estimators=20, random_state=23))
    explainer.fit(x_proper, y_proper)
    explainer.calibrate(x_cal, y_cal)

    result_without_targets = explainer.plot(
        x_query[:8],
        style=STYLE_ID,
        task="classification",
        show=True,
        position_precision=2,
    )
    result = explainer.plot(
        x_query[:8],
        y_query[:8],
        style=STYLE_ID,
        task="classification",
        show=True,
        position_precision=2,
    )

    assert result_without_targets.artifact["artifact_type"] == STYLE_ID
    assert result_without_targets.artifact["target_metadata"]["provided"] is False
    assert result.artifact["artifact_type"] == STYLE_ID
    assert result.artifact["target_metadata"]["target_kind"] == "class"
    assert result.figure.traces[-1].kwargs["name"] == "instances"
    assert result_without_targets.figure.shown is True
    assert result.figure.shown is True


def test_triangle_reference_can_be_disabled_for_probabilistic_render(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(
        _classification_payload(),
        task="classification",
        position_precision=2,
        show_triangle_reference=False,
    )

    result = plugin.render(plugin.build(context), context=context)

    assert len(result.figure.traces) == 1
    assert result.figure.traces[0].kwargs["name"] == "instances"


def test_triangle_reference_is_not_added_for_conformal_regression(monkeypatch):
    _install_fake_plotly(monkeypatch)
    _load_plugin(monkeypatch)
    plugin = registry.find_plot_plugin(STYLE_ID)
    context = _context(_conformal_regression_payload(), task="conformal_regression")

    result = plugin.render(plugin.build(context), context=context)

    assert len(result.figure.traces) == 1
    assert result.figure.traces[0].kwargs["name"] == "instances"
