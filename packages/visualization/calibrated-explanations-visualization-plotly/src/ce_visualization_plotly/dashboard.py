from __future__ import annotations

import webbrowser
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from calibrated_explanations.plugins.plots import PlotRenderContext
from calibrated_explanations.utils.exceptions import ConfigurationError

from .alternative_feature_summary import (
    AlternativeFeatureSummaryPlotBuilder,
    AlternativeFeatureSummaryPlotRenderer,
)
from .dashboard_cards import (
    DashboardCardDescriptor,
    find_dashboard_card,
    find_dashboard_card_by_style,
    iter_dashboard_cards,
)
from .ensured import LocalEnsuredPlotBuilder, LocalEnsuredPlotRenderer
from .instance_explorer import GlobalInstanceExplorerPlotBuilder
from .instance_explorer import build_figure as build_instance_explorer_figure
from .quadrant import UncertaintyQuadrantPlotBuilder, UncertaintyQuadrantPlotRenderer

_EXPLANATION_KINDS = ("factual", "alternative")

_LOCAL_CARD_BUILDERS = {
    "plotly.local.uncertainty_quadrant": UncertaintyQuadrantPlotBuilder,
    "plotly.local.ensured": LocalEnsuredPlotBuilder,
    "plotly.local.alternative_feature_summary": AlternativeFeatureSummaryPlotBuilder,
}
_LOCAL_CARD_RENDERERS = {
    "plotly.local.uncertainty_quadrant": UncertaintyQuadrantPlotRenderer,
    "plotly.local.ensured": LocalEnsuredPlotRenderer,
    "plotly.local.alternative_feature_summary": AlternativeFeatureSummaryPlotRenderer,
}


def _import_dash() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    try:
        from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html
    except ImportError as exc:  # pragma: no cover - depends on optional runtime extra
        raise RuntimeError(
            "Dash is required for live Plotly dashboards. Install the Plotly "
            "visualization package with its live dashboard extra."
        ) from exc
    return ALL, Dash, Input, Output, State, callback_context, dcc, html


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _slice_rows(x: Any, indices: Sequence[int]) -> Any:
    if hasattr(x, "iloc"):
        return x.iloc[list(indices)]
    try:
        import numpy as np

        return np.asarray(x)[list(indices)]
    except Exception:
        values = list(x)
        return [values[index] for index in indices]


def _resolve_local_cards(available_cards: Any) -> tuple[DashboardCardDescriptor, ...]:
    if available_cards == "auto":
        return tuple(
            descriptor for descriptor in iter_dashboard_cards() if descriptor.scope == "local"
        )
    descriptors: list[DashboardCardDescriptor] = []
    for card_name in _as_sequence(available_cards):
        descriptor = find_dashboard_card(str(card_name)) or find_dashboard_card_by_style(
            str(card_name)
        )
        if descriptor is None:
            raise ConfigurationError(f"Unknown dashboard card: {card_name}")
        if descriptor.scope == "local":
            descriptors.append(descriptor)
    return tuple(descriptors)


def _prediction_payload(
    explainer: Any,
    x: Any,
    y: Any,
    *,
    threshold: Any,
    task: str,
    class_id: Any,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    predict_kwargs = dict(options.get("predict_options", {}) or {})
    is_regularized = True
    learner = getattr(explainer, "learner", None)
    has_native_predict_proba = learner is not None and hasattr(learner, "predict_proba")
    if threshold is None and not has_native_predict_proba:
        predict, (low, high) = explainer.predict(x, uq_interval=True, **predict_kwargs)
        proba = None
        is_regularized = False
    else:
        proba, (low, high) = explainer.predict_proba(
            x,
            uq_interval=True,
            threshold=threshold,
            **predict_kwargs,
        )
        predict = None
    try:
        import numpy as np

        uncertainty = (
            (np.array(high) - np.array(low)) if low is not None and high is not None else None
        )
    except Exception:  # pragma: no cover - numpy is expected through CE
        uncertainty = None
    return {
        "proba": proba,
        "predict": predict,
        "low": low,
        "high": high,
        "uncertainty": uncertainty,
        "y": list(y) if y is not None else None,
        "is_regularized": is_regularized,
        "threshold": threshold,
        "class_labels": getattr(explainer, "class_labels", None),
        "class_id": class_id,
        "task": task,
        "x": x,
    }


def _global_artifact(
    explainer: Any,
    x: Any,
    y: Any,
    *,
    task: str,
    threshold: Any,
    class_id: Any,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _prediction_payload(
        explainer,
        x,
        y,
        threshold=threshold,
        task=task,
        class_id=class_id,
        options=options,
    )
    global_options = {
        "payload": payload,
        "task": task,
        "class_id": class_id,
        "threshold": threshold,
        "include_instance_records": True,
        **dict(options.get("global_options", {}) or {}),
    }
    return GlobalInstanceExplorerPlotBuilder().build(
        PlotRenderContext(
            explanation=None,
            instance_metadata=MappingProxyType({"type": "global", "dashboard_mode": "live_python"}),
            style="plotly.global.instance_explorer",
            intent=MappingProxyType({"type": "global"}),
            show=False,
            path=None,
            save_ext=None,
            options=MappingProxyType(global_options),
        )
    )


def _first_explanation(collection: Any) -> Any:
    explanations = getattr(collection, "explanations", None)
    if explanations is not None:
        return list(explanations)[0]
    try:
        return collection[0]
    except Exception:
        return collection


def _explain_instance(
    explainer: Any,
    x: Any,
    instance_index: int,
    *,
    kind: str,
    threshold: Any,
    max_rule_size: int,
    options: Mapping[str, Any],
) -> Any:
    row = _slice_rows(x, [instance_index])
    kwargs = dict(options.get(f"{kind}_options", {}) or {})
    if threshold is not None:
        kwargs.setdefault("threshold", threshold)
    if kind == "alternative":
        kwargs.setdefault("max_rule_size", max_rule_size)
        method = getattr(explainer, "explore_alternatives", None)
    else:
        method = getattr(explainer, "explain_factual", None)
    if not callable(method):
        raise ConfigurationError(f"Explainer does not expose a live {kind} explanation method.")
    return _first_explanation(method(row, **kwargs))


def _add_conjunctions(explanation: Any, *, max_rule_size: int, options: Mapping[str, Any]) -> None:
    method = getattr(explanation, "add_conjunctions", None)
    if not callable(method):
        raise ConfigurationError("Generated explanation does not support add_conjunctions.")
    kwargs = dict(options.get("conjunction_options", {}) or {})
    kwargs.setdefault("max_rule_size", max_rule_size)
    if "n_top_features" not in kwargs and options.get("conjunction_n_top_features") is not None:
        kwargs["n_top_features"] = options["conjunction_n_top_features"]
    method(**kwargs)


def _card_context(
    explanation: Any, descriptor: DashboardCardDescriptor, options: Mapping[str, Any]
) -> PlotRenderContext:
    intent_type = (
        "alternative" if "alternative_explanation" in set(descriptor.requires) else "factual"
    )
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance", "dashboard_mode": "live_python"}),
        style=descriptor.style,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(dict(options)),
    )


def _render_card(
    explanation: Any,
    descriptor: DashboardCardDescriptor,
    *,
    default_filter_top: int,
    include_conjunctions: bool,
    card_options: Mapping[str, Any],
) -> Any:
    builder_cls = _LOCAL_CARD_BUILDERS.get(descriptor.style)
    renderer_cls = _LOCAL_CARD_RENDERERS.get(descriptor.style)
    if builder_cls is None or renderer_cls is None:
        raise ConfigurationError(
            f"No live renderer is registered for dashboard card {descriptor.card_id!r}."
        )
    options = dict(descriptor.default_options)
    options.setdefault("filter_top", default_filter_top)
    options.update(dict(card_options.get(descriptor.card_id, {}) or {}))
    options.update(dict(card_options.get(descriptor.style, {}) or {}))
    if descriptor.card_id == "alternative_feature_summary":
        options["include_conjunctions"] = include_conjunctions
    context = _card_context(explanation, descriptor, options)
    artifact = builder_cls().build(context)
    result = renderer_cls().render(artifact, context=context)
    return result


def _summary_rows(record: Mapping[str, Any]) -> list[tuple[str, Any]]:
    metadata = dict(record.get("metadata", {}) or {})
    return [
        ("instance index", record.get("instance_index")),
        ("prediction", record.get("prediction")),
        ("calibrated interval", f"[{record.get('low')}, {record.get('high')}]"),
        ("uncertainty", record.get("interval_width")),
        (
            "task/posture",
            f"{metadata.get('task')} / {metadata.get('posture', metadata.get('task'))}",
        ),
        (
            "true label/target",
            record.get("true_label") or record.get("target_value") or metadata.get("target_label"),
        ),
    ]


def launch_instance_workspace(
    explainer: Any,
    x: Any,
    y: Any = None,
    *,
    available_cards: Any = "auto",
    task: str = "auto",
    threshold: Any = None,
    class_id: Any = None,
    max_rule_size_default: int = 3,
    default_filter_top: int = 20,
    host: str = "127.0.0.1",
    port: int = 8050,
    debug: bool = False,
    open_browser: bool = True,
    **options: Any,
) -> Any:
    """Launch a live Dash instance workspace for Plotly CE cards."""
    ALL, Dash, Input, Output, State, callback_context, dcc, html = _import_dash()  # noqa: N806
    descriptors = _resolve_local_cards(available_cards)
    card_options = dict(options.get("card_options", {}) or {})
    include_conjunctions = bool(options.get("include_conjunctions", False))
    global_artifact = _global_artifact(
        explainer,
        x,
        y,
        task=task,
        threshold=threshold,
        class_id=class_id,
        options=options,
    )
    records = list(global_artifact.get("instance_records", ()))
    record_by_index = {int(record["instance_index"]): record for record in records}
    figure = build_instance_explorer_figure(
        global_artifact, dict(global_artifact.get("options", {}) or {})
    )
    state: dict[tuple[int, str], Any] = {}
    conjunction_state: set[int] = set()
    workspace_items: list[dict[str, Any]] = []

    app = Dash(__name__, suppress_callback_exceptions=True)
    app.title = "CE Plotly instance workspace"
    app.layout = html.Div(
        [
            dcc.Store(
                id="ce-selected-instance", data=records[0]["instance_index"] if records else None
            ),
            dcc.Store(id="ce-workspace-items", data=[]),
            dcc.Store(id="ce-live-explanation-status", data={}),
            html.Div(
                [
                    html.Div(
                        [dcc.Graph(id="ce-global-instance-explorer", figure=figure)],
                        className="ce-live-overview",
                    ),
                    html.Div(id="ce-live-workspace", className="ce-live-workspace"),
                ],
                className="ce-live-main",
            ),
            html.Aside(
                [
                    html.Label("Instance", htmlFor="ce-live-instance-select"),
                    dcc.Dropdown(
                        id="ce-live-instance-select",
                        options=[
                            {
                                "label": f"Instance {record['instance_index']}",
                                "value": int(record["instance_index"]),
                            }
                            for record in records
                        ],
                        value=records[0]["instance_index"] if records else None,
                        clearable=False,
                    ),
                    html.Div(id="ce-live-summary"),
                    html.Label("Card", htmlFor="ce-live-card-select"),
                    dcc.Dropdown(
                        id="ce-live-card-select",
                        options=[
                            {"label": descriptor.label, "value": descriptor.card_id}
                            for descriptor in descriptors
                        ],
                        value=descriptors[0].card_id if descriptors else None,
                        clearable=False,
                    ),
                    html.Button("Add Card", id="ce-live-add-card", n_clicks=0),
                    html.Button("Explain and explore", id="ce-live-explain-explore", n_clicks=0),
                    html.Button(
                        "Add conjunctions", id="ce-live-add-conjunctions", n_clicks=0, disabled=True
                    ),
                    html.Div(id="ce-live-status"),
                ],
                className="ce-live-panel",
            ),
        ],
        className="ce-live-dashboard",
    )

    def _status_payload() -> dict[str, dict[str, bool]]:
        return {
            str(instance_index): {
                "has_factual": (instance_index, "factual") in state,
                "has_alternative": (instance_index, "alternative") in state,
                "has_conjunctions": instance_index in conjunction_state,
            }
            for instance_index in sorted({key[0] for key in state} | conjunction_state)
        }

    def _ensure_explanation_kind(instance_index: int, kind: str) -> Any:
        key = (int(instance_index), kind)
        if key not in state:
            state[key] = _explain_instance(
                explainer,
                x,
                int(instance_index),
                kind=kind,
                threshold=threshold,
                max_rule_size=int(options.get("max_rule_size", max_rule_size_default)),
                options=options,
            )
        return state[key]

    def _explanation_for_card(instance_index: int, descriptor: DashboardCardDescriptor) -> Any:
        is_alternative = "alternative_explanation" in set(descriptor.requires)
        kind = "alternative" if is_alternative else "factual"
        key = (int(instance_index), kind)
        if key not in state:
            raise ConfigurationError("Click Explain and explore before adding a card.")
        return state[key]

    @app.callback(
        Output("ce-live-instance-select", "value"),
        Output("ce-selected-instance", "data"),
        Input("ce-global-instance-explorer", "clickData"),
        Input("ce-live-instance-select", "value"),
        prevent_initial_call=False,
    )
    def _select_instance(click_data: Any, dropdown_value: Any) -> tuple[Any, Any]:
        selected = dropdown_value
        if click_data and click_data.get("points"):
            point = click_data["points"][0]
            point_index = int(point.get("pointIndex", 0))
            markers = list(global_artifact.get("marker_records", ()))
            if 0 <= point_index < len(markers) and markers[point_index].get("instance_indices"):
                selected = int(markers[point_index]["instance_indices"][0])
        return selected, selected

    @app.callback(
        Output("ce-live-summary", "children"),
        Input("ce-selected-instance", "data"),
    )
    def _render_summary(instance_index: Any) -> Any:
        record = record_by_index.get(int(instance_index)) if instance_index is not None else None
        if record is None:
            return html.P("No instance selected.")
        return html.Dl(
            [
                item
                for row in _summary_rows(record)
                for item in (html.Dt(row[0]), html.Dd(str(row[1])))
            ]
        )

    @app.callback(
        Output("ce-workspace-items", "data"),
        Output("ce-live-explanation-status", "data"),
        Output("ce-live-status", "children"),
        Input("ce-live-add-card", "n_clicks"),
        Input("ce-live-explain-explore", "n_clicks"),
        Input("ce-live-add-conjunctions", "n_clicks"),
        State("ce-selected-instance", "data"),
        State("ce-live-card-select", "value"),
        State("ce-workspace-items", "data"),
        prevent_initial_call=True,
    )
    def _handle_workspace_action(
        _add_clicks: int,
        _explain_clicks: int,
        _conjunction_clicks: int,
        instance_index: Any,
        card_id: str,
        items: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, bool]], str]:
        current_items = list(items or [])
        if instance_index is None or not card_id:
            return current_items, _status_payload(), "Select an instance and a card."
        triggered_id = getattr(callback_context, "triggered_id", None)
        selected_index = int(instance_index)
        max_rule_size = int(options.get("max_rule_size", max_rule_size_default))
        if triggered_id == "ce-live-explain-explore":
            for kind in _EXPLANATION_KINDS:
                _ensure_explanation_kind(selected_index, kind)
            return (
                current_items,
                _status_payload(),
                f"Generated factual and alternative explanations for instance {selected_index}.",
            )
        if triggered_id == "ce-live-add-conjunctions":
            missing = [kind for kind in _EXPLANATION_KINDS if (selected_index, kind) not in state]
            if missing:
                return (
                    current_items,
                    _status_payload(),
                    "Click Explain and explore before adding conjunctions.",
                )
            for kind in _EXPLANATION_KINDS:
                _add_conjunctions(
                    state[(selected_index, kind)], max_rule_size=max_rule_size, options=options
                )
            conjunction_state.add(selected_index)
            return (
                current_items,
                _status_payload(),
                f"Added conjunctions to factual and alternative explanations for instance {selected_index}.",  # noqa: E501
            )
        descriptor = find_dashboard_card(card_id)
        if descriptor is None:
            return current_items, _status_payload(), f"Unknown card: {card_id}"
        try:
            explanation = _explanation_for_card(selected_index, descriptor)
        except ConfigurationError as exc:
            return current_items, _status_payload(), str(exc)
        result = _render_card(
            explanation,
            descriptor,
            default_filter_top=default_filter_top,
            include_conjunctions=include_conjunctions or selected_index in conjunction_state,
            card_options=card_options,
        )
        item_id = f"{selected_index}-{descriptor.card_id}-{len(workspace_items)}"
        workspace_items.append(
            {
                "id": item_id,
                "instance_index": selected_index,
                "card_id": descriptor.card_id,
                "label": descriptor.label,
                "figure": result.figure,
                "html": result.extras.get("html") if isinstance(result.extras, Mapping) else None,
            }
        )
        next_items = list(current_items)
        next_items.append({"id": item_id})
        return (
            next_items,
            _status_payload(),
            f"Added {descriptor.label} for instance {selected_index}.",
        )

    @app.callback(
        Output("ce-live-add-conjunctions", "disabled"),
        Input("ce-selected-instance", "data"),
        Input("ce-live-explanation-status", "data"),
    )
    def _toggle_conjunction_button(instance_index: Any, status: Mapping[str, Any] | None) -> bool:
        if instance_index is None:
            return True
        selected = dict((status or {}).get(str(int(instance_index)), {}) or {})
        return not (selected.get("has_factual") and selected.get("has_alternative"))

    @app.callback(
        Output("ce-live-workspace", "children"),
        Input("ce-workspace-items", "data"),
    )
    def _render_workspace(items: list[dict[str, Any]] | None) -> Any:
        rendered = []
        item_ids = [item["id"] for item in (items or [])]
        by_id = {item["id"]: item for item in workspace_items}
        for item_id in item_ids:
            item = by_id.get(item_id)
            if item is None:
                continue
            body = (
                html.Iframe(
                    srcDoc=item["html"], style={"width": "100%", "height": "520px", "border": "0"}
                )
                if item.get("html")
                else dcc.Graph(figure=item["figure"])
            )
            rendered.append(
                html.Section(
                    [
                        html.Header(
                            [
                                html.H3(f"{item['label']} - instance {item['instance_index']}"),
                                html.Button(
                                    "Up", id={"type": "ce-live-move-card-up", "id": item_id}
                                ),
                                html.Button(
                                    "Down", id={"type": "ce-live-move-card-down", "id": item_id}
                                ),
                                html.Button(
                                    "Remove", id={"type": "ce-live-remove-card", "id": item_id}
                                ),
                            ]
                        ),
                        body,
                    ],
                    className="ce-live-card",
                )
            )
        return rendered or html.P("Select an instance and add a card to the workspace.")

    @app.callback(
        Output("ce-workspace-items", "data", allow_duplicate=True),
        Input({"type": "ce-live-remove-card", "id": ALL}, "n_clicks"),
        Input({"type": "ce-live-move-card-up", "id": ALL}, "n_clicks"),
        Input({"type": "ce-live-move-card-down", "id": ALL}, "n_clicks"),
        State("ce-workspace-items", "data"),
        prevent_initial_call=True,
    )
    def _edit_workspace(
        _remove_clicks: list[int] | None,
        _up_clicks: list[int] | None,
        _down_clicks: list[int] | None,
        items: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        current = list(items or [])
        triggered_id = getattr(callback_context, "triggered_id", None)
        if not isinstance(triggered_id, dict):
            return current
        item_id = triggered_id.get("id")
        action = triggered_id.get("type")
        index = next((pos for pos, item in enumerate(current) if item.get("id") == item_id), None)
        if index is None:
            return current
        if action == "ce-live-remove-card":
            return [item for item in current if item.get("id") != item_id]
        if action == "ce-live-move-card-up" and index > 0:
            current[index - 1], current[index] = current[index], current[index - 1]
        if action == "ce-live-move-card-down" and index < len(current) - 1:
            current[index + 1], current[index] = current[index], current[index + 1]
        return current

    app.ce_workspace_state = {
        "records": records,
        "global_artifact": global_artifact,
        "available_cards": descriptors,
        "explanations": state,
        "workspace_items": workspace_items,
    }
    app.ce_workspace_url = f"http://{host}:{port}"

    if bool(options.get("run_server", True)):
        if open_browser:
            webbrowser.open(app.ce_workspace_url)
        runner = getattr(app, "run", None) or getattr(app, "run_server", None)
        if not callable(runner):
            raise RuntimeError("Dash app does not expose run or run_server.")
        runner(host=host, port=port, debug=debug)
    return app


__all__ = ["launch_instance_workspace"]
