from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


def _load_dashboard(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    return importlib.import_module("ce_visualization_plotly.dashboard")


def _install_fake_plotly(monkeypatch):
    class FakeScatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFigure:
        def __init__(self, **_kwargs):
            self.traces = []
            self.layout = {}

        def add_trace(self, trace, **_kwargs):
            self.traces.append(trace)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def add_vline(self, **_kwargs):
            pass

        def add_hline(self, **_kwargs):
            pass

        def add_annotation(self, **_kwargs):
            pass

    graph_objects_mod = types.ModuleType("plotly.graph_objects")
    graph_objects_mod.Figure = FakeFigure
    graph_objects_mod.Scatter = FakeScatter
    plotly_mod = types.ModuleType("plotly")
    monkeypatch.setitem(sys.modules, "plotly", plotly_mod)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_mod)


def _install_fake_dash(monkeypatch):
    class FakeComponentFactory:
        def __getattr__(self, name):
            def make_component(*children, **props):
                return {"type": name, "children": children, "props": props}

            return make_component

    class FakeDash:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.callbacks = []
            self.layout = None
            self.runs = []
            self.title = None

        def callback(self, *args, **kwargs):
            def decorate(func):
                self.callbacks.append({"args": args, "kwargs": kwargs, "func": func})
                return func

            return decorate

        def run(self, **kwargs):
            self.runs.append(kwargs)

    class FakeDependency:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    dash_mod = types.ModuleType("dash")
    dash_mod.ALL = object()
    dash_mod.Dash = FakeDash
    dash_mod.Input = FakeDependency
    dash_mod.Output = FakeDependency
    dash_mod.State = FakeDependency
    dash_mod.callback_context = types.SimpleNamespace(triggered_id=None)
    dash_mod.dcc = FakeComponentFactory()
    dash_mod.html = FakeComponentFactory()
    monkeypatch.setitem(sys.modules, "dash", dash_mod)
    return FakeDash


class FakeLearner:
    def predict_proba(self, _x):
        return []


class FakeExplainer:
    learner = FakeLearner()
    class_labels = None

    def __init__(self):
        self.factual_calls = []
        self.alternative_calls = []

    def predict_proba(self, x, **_kwargs):
        rows = len(x)
        proba = [[0.4, 0.6 + index * 0.05] for index in range(rows)]
        low = [[0.3, 0.5] for _ in range(rows)]
        high = [[0.5, 0.8] for _ in range(rows)]
        return proba, (low, high)

    def explain_factual(self, x, **kwargs):
        self.factual_calls.append((x, kwargs))
        return types.SimpleNamespace(explanations=[FakeExplanation(is_alternative=False)])

    def explore_alternatives(self, x, **kwargs):
        self.alternative_calls.append((x, kwargs))
        return types.SimpleNamespace(explanations=[FakeExplanation(is_alternative=True)])


class FakeExplanation:
    def __init__(self, *, is_alternative):
        self.index = 0
        self._is_alternative = is_alternative
        self.conjunction_calls = []

    def is_alternative(self):
        return self._is_alternative

    def add_conjunctions(self, **kwargs):
        self.conjunction_calls.append(kwargs)


def test_launch_instance_workspace_requires_dash(monkeypatch):
    monkeypatch.setitem(sys.modules, "dash", None)
    dashboard = _load_dashboard(monkeypatch)

    with pytest.raises(RuntimeError, match="Dash is required"):
        dashboard.launch_instance_workspace(FakeExplainer(), [[1, 2]], run_server=False)


def test_launch_instance_workspace_builds_app_without_running(monkeypatch):
    _install_fake_dash(monkeypatch)
    _install_fake_plotly(monkeypatch)
    dashboard = _load_dashboard(monkeypatch)

    app = dashboard.launch_instance_workspace(
        FakeExplainer(),
        [[1, 2], [3, 4]],
        y=[0, 1],
        available_cards=["local_uncertainty_quadrant", "local_ensured"],
        run_server=False,
        open_browser=False,
    )

    assert app.title == "CE Plotly instance workspace"
    assert app.runs == []
    assert len(app.ce_workspace_state["records"]) == 2
    assert [card.card_id for card in app.ce_workspace_state["available_cards"]] == [
        "uncertainty_quadrant",
        "ensured",
    ]
    assert app.ce_workspace_url == "http://127.0.0.1:8050"
    assert len(app.callbacks) >= 4


def test_launch_instance_workspace_can_start_server(monkeypatch):
    _install_fake_dash(monkeypatch)
    _install_fake_plotly(monkeypatch)
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    dashboard = _load_dashboard(monkeypatch)

    app = dashboard.launch_instance_workspace(
        FakeExplainer(),
        [[1, 2]],
        run_server=True,
        open_browser=True,
        host="0.0.0.0",
        port=8099,
        debug=True,
    )

    assert opened == ["http://0.0.0.0:8099"]
    assert app.runs == [{"host": "0.0.0.0", "port": 8099, "debug": True}]


def test_live_workspace_actions_do_not_add_cards_until_add_card(monkeypatch):
    _install_fake_dash(monkeypatch)
    _install_fake_plotly(monkeypatch)
    dashboard = _load_dashboard(monkeypatch)
    fake_explainer = FakeExplainer()
    monkeypatch.setattr(
        dashboard,
        "_render_card",
        lambda *_args, **_kwargs: types.SimpleNamespace(figure={"data": []}, extras={}),
    )

    app = dashboard.launch_instance_workspace(
        fake_explainer,
        [[1, 2], [3, 4]],
        available_cards=["local_uncertainty_quadrant", "local_ensured"],
        run_server=False,
        open_browser=False,
        max_rule_size=3,
    )
    handler = next(callback["func"] for callback in app.callbacks if callback["func"].__name__ == "_handle_workspace_action")
    toggle = next(callback["func"] for callback in app.callbacks if callback["func"].__name__ == "_toggle_conjunction_button")
    dash_mod = sys.modules["dash"]

    dash_mod.callback_context.triggered_id = "ce-live-add-card"
    items, status, message = handler(1, 0, 0, 0, "uncertainty_quadrant", [])

    assert items == []
    assert status == {}
    assert message == "Click Explain and explore before adding a card."
    assert toggle(0, status) is True

    dash_mod.callback_context.triggered_id = "ce-live-explain-explore"
    items, status, message = handler(1, 1, 0, 0, "uncertainty_quadrant", items)

    assert items == []
    assert status["0"]["has_factual"] is True
    assert status["0"]["has_alternative"] is True
    assert status["0"]["has_conjunctions"] is False
    assert message == "Generated factual and alternative explanations for instance 0."
    assert len(fake_explainer.factual_calls) == 1
    assert len(fake_explainer.alternative_calls) == 1
    assert toggle(0, status) is False

    dash_mod.callback_context.triggered_id = "ce-live-add-conjunctions"
    items, status, message = handler(1, 1, 1, 0, "uncertainty_quadrant", items)

    assert items == []
    assert status["0"]["has_conjunctions"] is True
    assert message == "Added conjunctions to factual and alternative explanations for instance 0."
    assert app.ce_workspace_state["explanations"][(0, "factual")].conjunction_calls == [{"max_rule_size": 3}]
    assert app.ce_workspace_state["explanations"][(0, "alternative")].conjunction_calls == [{"max_rule_size": 3}]

    dash_mod.callback_context.triggered_id = "ce-live-add-card"
    items, status, message = handler(2, 1, 1, 0, "uncertainty_quadrant", items)

    assert items == [{"id": "0-uncertainty_quadrant-0"}]
    assert status["0"]["has_conjunctions"] is True
    assert message == "Added Uncertainty Quadrant for instance 0."
