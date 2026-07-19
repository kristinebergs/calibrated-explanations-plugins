from __future__ import annotations

import json
from html import escape
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)
from calibrated_explanations.utils.exceptions import ConfigurationError

from ._version import PACKAGE_VERSION, PROVIDER
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
from .factual_bars import STYLE_ID as FACTUAL_BARS_STYLE_ID
from .factual_bars import LocalFactualBarsPlotBuilder, LocalFactualBarsPlotRenderer
from .factual_simple import STYLE_ID as FACTUAL_SIMPLE_STYLE_ID
from .factual_simple import LocalFactualSimplePlotBuilder, LocalFactualSimplePlotRenderer
from .instance_explorer import (
    GlobalInstanceExplorerPlotBuilder,
)
from .instance_explorer import (
    build_figure as build_global_instance_explorer_figure,
)
from .quadrant import UncertaintyQuadrantPlotBuilder, UncertaintyQuadrantPlotRenderer

STYLE_ID = "plotly.dashboard.instance_workspace"
BUILDER_ID = "official.visualization.plotly.dashboard.instance_workspace.builder"
RENDERER_ID = "official.visualization.plotly.dashboard.instance_workspace.renderer"
ARTIFACT_TYPE = STYLE_ID
ARTIFACT_VERSION = "0.1.0"
STANDALONE_LIMITATION = (
    "Standalone mode can inspect precomputed explanations only. On-demand "
    "factual/alternative generation requires live dashboard mode."
)

_VALID_PRECOMPUTE = {"none", "selected", "top_uncertain", "all"}
_VALID_LAYOUTS = {"default", "wide", "compact"}
_LOCAL_CARD_BUILDERS = {
    "plotly.local.uncertainty_quadrant": UncertaintyQuadrantPlotBuilder,
    FACTUAL_BARS_STYLE_ID: LocalFactualBarsPlotBuilder,
    FACTUAL_SIMPLE_STYLE_ID: LocalFactualSimplePlotBuilder,
    "plotly.local.ensured": LocalEnsuredPlotBuilder,
    "plotly.local.alternative_feature_summary": AlternativeFeatureSummaryPlotBuilder,
}
_LOCAL_CARD_RENDERERS = {
    "plotly.local.uncertainty_quadrant": UncertaintyQuadrantPlotRenderer,
    FACTUAL_BARS_STYLE_ID: LocalFactualBarsPlotRenderer,
    FACTUAL_SIMPLE_STYLE_ID: LocalFactualSimplePlotRenderer,
    "plotly.local.ensured": LocalEnsuredPlotRenderer,
    "plotly.local.alternative_feature_summary": AlternativeFeatureSummaryPlotRenderer,
}


def _as_options(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _is_alternative(explanation: Any) -> bool:
    marker = getattr(explanation, "is_alternative", None)
    return bool(marker() if callable(marker) else marker)


def _items_from_payload(payload: Any, *names: str) -> list[Any]:
    for name in names:
        values = getattr(payload, name, None)
        if values is None and isinstance(payload, Mapping):
            values = payload.get(name)
        if values is not None:
            return _as_sequence(values)
    return []


def _item_by_instance_index(items: Sequence[Any], instance_index: int) -> Any | None:
    for item in items:
        if getattr(item, "index", None) == instance_index:
            return item
        if isinstance(item, Mapping) and item.get("index") == instance_index:
            return item
    if 0 <= instance_index < len(items):
        return items[instance_index]
    return None


def _local_explanation_for(payload: Any, instance_index: int, *, alternative: bool) -> Any | None:
    if alternative:
        candidates = _items_from_payload(
            payload,
            "alternative_explanation",
            "alternative_explanations",
            "alternatives",
            "alternative",
        )
        if not candidates:
            candidates = [
                item
                for item in _items_from_payload(payload, "explanations", "instances")
                if _is_alternative(item)
            ]
    else:
        candidates = _items_from_payload(
            payload,
            "factual_explanation",
            "factual_explanations",
            "factual",
            "explanations",
            "instances",
        )
        candidates = [item for item in candidates if not _is_alternative(item)]
    if (
        not candidates
        and not isinstance(payload, Mapping)
        and _is_alternative(payload) == alternative
    ):
        return payload
    return _item_by_instance_index(candidates, instance_index)


def _prediction_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("metadata", {}) or {})
    return {
        "instance_index": record.get("instance_index"),
        "prediction": record.get("prediction"),
        "low": record.get("low"),
        "high": record.get("high"),
        "uncertainty": record.get("interval_width"),
        "task": metadata.get("task"),
        "posture": metadata.get("posture", metadata.get("task")),
        "true_label": record.get("true_label"),
        "target_value": record.get("target_value"),
        "target": metadata.get("target"),
        "target_label": metadata.get("target_label"),
    }


def _selected_descriptors(options: Mapping[str, Any]) -> tuple[DashboardCardDescriptor, ...]:
    include_factual = bool(options.get("include_factual", True))
    include_alternatives = bool(options.get("include_alternatives", True))
    requested = options.get("available_cards", "auto")
    if requested == "auto":
        descriptors = [
            descriptor for descriptor in iter_dashboard_cards() if descriptor.scope == "local"
        ]
    else:
        descriptors = []
        for card_name in _as_sequence(requested):
            descriptor = find_dashboard_card(str(card_name)) or find_dashboard_card_by_style(
                str(card_name)
            )
            if descriptor is None:
                raise ConfigurationError(f"Unknown dashboard card: {card_name}")
            if descriptor.scope == "local":
                descriptors.append(descriptor)
    result: list[DashboardCardDescriptor] = []
    for descriptor in descriptors:
        requires = set(descriptor.requires)
        if "factual_explanation" in requires and not include_factual:
            continue
        if "alternative_explanation" in requires and not include_alternatives:
            continue
        result.append(descriptor)
    return tuple(result)


def _precompute_indices(
    records: Sequence[Mapping[str, Any]],
    options: Mapping[str, Any],
) -> tuple[list[int], list[str]]:
    mode = str(options.get("precompute", "none"))
    if mode not in _VALID_PRECOMPUTE:
        raise ConfigurationError("precompute must be one of none, selected, top_uncertain, or all.")
    if mode == "none":
        return [], []

    max_instances = int(options.get("max_precomputed_instances", 20))
    allow_large = bool(options.get("allow_large_precompute", False))
    warnings: list[str] = []
    available_indices = [int(record["instance_index"]) for record in records]
    if mode == "selected":
        selected = [int(index) for index in _as_sequence(options.get("selected_instance_indices"))]
    elif mode == "top_uncertain":
        selected = [
            int(record["instance_index"])
            for record in sorted(
                records, key=lambda item: float(item.get("interval_width", 0.0)), reverse=True
            )
        ][:max_instances]
    else:
        selected = available_indices

    selected = [index for index in dict.fromkeys(selected) if index in available_indices]
    if len(selected) > max_instances and not allow_large:
        raise ConfigurationError(
            f"Precomputing {len(selected)} instances exceeds max_precomputed_instances="
            f"{max_instances}. Set allow_large_precompute=True to override."
        )
    if (
        len(selected) > max_instances
        and allow_large
        and bool(options.get("show_limit_warnings", True))
    ):
        warnings.append(
            f"Large standalone precompute enabled for {len(selected)} instances; HTML export may be heavy."
        )
    return selected, warnings


def _card_context(
    explanation: Any,
    descriptor: DashboardCardDescriptor,
    options: Mapping[str, Any],
    *,
    intent_type: str,
) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType(
            {"type": "instance", "dashboard_mode": "standalone_html"}
        ),
        style=descriptor.style,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(dict(options)),
    )


def _options_for_card(
    descriptor: DashboardCardDescriptor,
    dashboard_options: Mapping[str, Any],
) -> dict[str, Any]:
    card_options = _as_options(dashboard_options.get("card_options"))
    options = dict(descriptor.default_options)
    options.update(_as_options(card_options.get(descriptor.card_id)))
    options.update(_as_options(card_options.get(descriptor.style)))
    if descriptor.card_id == "alternative_feature_summary":
        options.setdefault(
            "include_conjunctions", bool(dashboard_options.get("include_conjunctions", False))
        )
    return options


def _build_card_artifact(
    payload: Any,
    instance_index: int,
    descriptor: DashboardCardDescriptor,
    dashboard_options: Mapping[str, Any],
) -> dict[str, Any]:
    requires = set(descriptor.requires)
    is_alternative_card = "alternative_explanation" in requires
    explanation = _local_explanation_for(payload, instance_index, alternative=is_alternative_card)
    if explanation is None:
        return {
            "card_id": descriptor.card_id,
            "style": descriptor.style,
            "label": descriptor.label,
            "available": False,
            "reason": (
                "alternative explanation unavailable"
                if is_alternative_card
                else "factual explanation unavailable"
            ),
        }
    options = _options_for_card(descriptor, dashboard_options)
    builder_cls = _LOCAL_CARD_BUILDERS.get(descriptor.style)
    if builder_cls is None:
        return {
            "card_id": descriptor.card_id,
            "style": descriptor.style,
            "label": descriptor.label,
            "available": False,
            "reason": "no standalone builder registered for card",
        }
    try:
        artifact = builder_cls().build(
            _card_context(
                explanation,
                descriptor,
                options,
                intent_type="alternative" if is_alternative_card else "factual",
            )
        )
    except Exception as exc:  # pragma: no cover - defensive for mixed CE versions
        return {
            "card_id": descriptor.card_id,
            "style": descriptor.style,
            "label": descriptor.label,
            "available": False,
            "reason": str(exc),
        }
    return {
        "card_id": descriptor.card_id,
        "style": descriptor.style,
        "label": descriptor.label,
        "description": descriptor.description,
        "requires": descriptor.requires,
        "available": True,
        "options": options,
        "artifact": artifact,
    }


class InstanceWorkspaceDashboardBuilder(PlotBuilder):
    """Build a standalone dashboard artifact from global and precomputed local data."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": PACKAGE_VERSION,
        "provider": PROVIDER,
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "intent": "dashboard",
        "output_formats": ("html",),
        "capabilities": ["plot:builder"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        options = dict(context.options)
        dashboard_mode = str(options.get("dashboard_mode", "standalone_html"))
        if dashboard_mode != "standalone_html":
            raise ConfigurationError("Mode A supports dashboard_mode='standalone_html' only.")
        layout_preset = str(options.get("layout_preset", "default"))
        if layout_preset not in _VALID_LAYOUTS:
            raise ConfigurationError("layout_preset must be one of default, wide, or compact.")

        global_descriptor = find_dashboard_card("instance_explorer")
        assert global_descriptor is not None
        global_options = dict(global_descriptor.default_options)
        global_options.update(_as_options(options.get("global_options")))
        global_options["include_instance_records"] = True
        global_context = PlotRenderContext(
            explanation=context.explanation,
            instance_metadata=MappingProxyType(
                {"type": "global", "dashboard_mode": dashboard_mode}
            ),
            style=global_descriptor.style,
            intent=MappingProxyType({"type": "global"}),
            show=False,
            path=None,
            save_ext=None,
            options=MappingProxyType(global_options),
        )
        global_artifact = GlobalInstanceExplorerPlotBuilder().build(global_context)
        records = list(global_artifact.get("instance_records", ()))
        selected_indices, limit_warnings = _precompute_indices(records, options)
        descriptors = _selected_descriptors(options)
        record_by_index = {int(record["instance_index"]): record for record in records}

        precomputed: dict[str, Any] = {}
        for instance_index in selected_indices:
            record = record_by_index[instance_index]
            cards = [
                _build_card_artifact(context.explanation, instance_index, descriptor, options)
                for descriptor in descriptors
                if descriptor.supports_task(record.get("metadata", {}).get("task"))
            ][: int(options.get("max_cards_per_instance", 4))]
            precomputed[str(instance_index)] = {
                "instance_index": instance_index,
                "factual_summary": _prediction_summary(record),
                "alternative_summary": {},
                "cards": cards,
            }

        card_manifest = [
            {
                "card_id": descriptor.card_id,
                "style": descriptor.style,
                "label": descriptor.label,
                "description": descriptor.description,
                "scope": descriptor.scope,
                "requires": descriptor.requires,
                "supports_tasks": descriptor.supports_tasks,
                "default_options": dict(descriptor.default_options),
                "experimental": descriptor.experimental,
            }
            for descriptor in descriptors
        ]
        return {
            "artifact_type": ARTIFACT_TYPE,
            "artifact_version": ARTIFACT_VERSION,
            "dashboard_mode": dashboard_mode,
            "global_artifact": global_artifact,
            "instance_records": records,
            "precomputed_local": precomputed,
            "card_manifest": card_manifest,
            "layout": {
                "preset": layout_preset,
                "allow_card_reorder": bool(options.get("allow_card_reorder", True)),
                "allow_card_remove": bool(options.get("allow_card_remove", True)),
                "max_cards_per_instance": int(options.get("max_cards_per_instance", 4)),
            },
            "interaction_capabilities": {
                "standalone_html": True,
                "global_instance_selection": True,
                "precomputed_local_cards": bool(precomputed),
                "card_reorder": bool(options.get("allow_card_reorder", True)),
                "card_remove": bool(options.get("allow_card_remove", True)),
                "live_computation": False,
            },
            "limits": {
                "precompute": str(options.get("precompute", "none")),
                "max_precomputed_instances": int(options.get("max_precomputed_instances", 20)),
                "precomputed_instance_count": len(precomputed),
                "allow_large_precompute": bool(options.get("allow_large_precompute", False)),
                "warnings": limit_warnings,
            },
            "metadata": {
                "created_by": STYLE_ID,
                "limitation": STANDALONE_LIMITATION,
                "num_instances": len(records),
            },
        }


def _json_default(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, MappingProxyType):
        return dict(value)
    if isinstance(value, tuple):
        return list(value)
    return str(value)


def _figure_html(fig: Any, *, include_plotlyjs: bool | str, div_id: str) -> str:
    if hasattr(fig, "to_html"):
        return fig.to_html(
            full_html=False,
            include_plotlyjs=include_plotlyjs,
            div_id=div_id,
        )
    import plotly.io as plotly_io

    return plotly_io.to_html(
        fig,
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        div_id=div_id,
    )


def _card_html(card: Mapping[str, Any], *, div_id: str) -> str:
    if not card.get("available"):
        return (
            f'<div class="ce-workspace-card ce-workspace-card--unavailable">'
            f'<h3>{escape(str(card.get("label", "Unavailable card")))}</h3>'
            f'<p>{escape(str(card.get("reason", "Unavailable")))}</p></div>'
        )
    renderer_cls = _LOCAL_CARD_RENDERERS.get(str(card.get("style")))
    descriptor = find_dashboard_card(str(card.get("card_id"))) or find_dashboard_card_by_style(
        str(card.get("style"))
    )
    if renderer_cls is None or descriptor is None:
        return ""
    context = _card_context(
        None,
        descriptor,
        dict(card.get("options", {}) or {}),
        intent_type="alternative"
        if "alternative_explanation" in set(descriptor.requires)
        else "factual",
    )
    result = renderer_cls().render(dict(card["artifact"]), context=context)
    shell_html = result.extras.get("html") if isinstance(result.extras, Mapping) else None
    if shell_html:
        figure_html = str(shell_html)
    else:
        figure_html = _figure_html(result.figure, include_plotlyjs=False, div_id=div_id)
    return (
        f'<section class="ce-workspace-card" data-card-id="{escape(str(card.get("card_id")))}">'
        f'<header><h3>{escape(str(card.get("label")))}</h3>'
        '<button type="button" class="ce-card-remove" data-card-remove>Remove</button></header>'
        f"{figure_html}</section>"
    )


def _build_card_fragments(artifact: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    fragments: dict[str, list[dict[str, str]]] = {}
    for instance_index, payload in dict(artifact.get("precomputed_local", {}) or {}).items():
        fragments[str(instance_index)] = []
        for position, card in enumerate(payload.get("cards", ())):
            div_id = f"ce-card-{instance_index}-{position}"
            fragments[str(instance_index)].append(
                {
                    "card_id": str(card.get("card_id")),
                    "label": str(card.get("label")),
                    "available": bool(card.get("available")),
                    "html": _card_html(card, div_id=div_id),
                }
            )
    return fragments


def build_dashboard_html(artifact: PlotArtifact) -> str:
    global_figure = build_global_instance_explorer_figure(
        dict(artifact["global_artifact"]),
        dict(artifact.get("global_artifact", {}).get("options", {}) or {}),
    )
    global_html = _figure_html(global_figure, include_plotlyjs=True, div_id="ce-instance-overview")
    fragments = _build_card_fragments(artifact)
    data_payload = {
        "records": artifact.get("instance_records", ()),
        "globalMarkers": artifact.get("global_artifact", {}).get("marker_records", ()),
        "precomputed": {
            key: {
                "summary": value.get("factual_summary", {}),
                "cards": [
                    {
                        "card_id": card.get("card_id"),
                        "label": card.get("label"),
                        "available": card.get("available"),
                        "reason": card.get("reason"),
                    }
                    for card in value.get("cards", ())
                ],
            }
            for key, value in dict(artifact.get("precomputed_local", {}) or {}).items()
        },
        "cardFragments": fragments,
        "layout": artifact.get("layout", {}),
        "limits": artifact.get("limits", {}),
        "limitation": STANDALONE_LIMITATION,
    }
    payload_json = json.dumps(data_payload, default=_json_default)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plotly instance workspace</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2937; background: #f5f7fb; }}
    .ce-dashboard {{ min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1fr) 360px; }}
    .ce-main {{ padding: 18px; min-width: 0; }}
    .ce-panel {{ border-left: 1px solid #d7dde8; background: #ffffff; padding: 16px; overflow: auto; }}
    .ce-notice {{ margin: 0 0 12px; padding: 10px 12px; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; font-size: 13px; }}
    .ce-overview {{ background: #ffffff; border: 1px solid #d7dde8; border-radius: 6px; padding: 8px; }}
    .ce-workspace {{ margin-top: 14px; display: grid; gap: 12px; }}
    .ce-workspace-card {{ background: #ffffff; border: 1px solid #d7dde8; border-radius: 6px; padding: 10px; }}
    .ce-workspace-card header {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .ce-workspace-card h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .ce-kv {{ display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 6px 10px; font-size: 13px; }}
    .ce-kv dt {{ color: #667085; }}
    .ce-kv dd {{ margin: 0; font-weight: 600; word-break: break-word; }}
    .ce-card-list {{ display: grid; gap: 8px; margin-top: 14px; }}
    button, select {{ font: inherit; }}
    button {{ border: 1px solid #c4ccd8; background: #f8fafc; border-radius: 5px; padding: 6px 9px; cursor: pointer; }}
    button:disabled {{ cursor: not-allowed; opacity: 0.45; }}
    .ce-card-remove {{ display: none; }}
    @media (max-width: 900px) {{ .ce-dashboard {{ grid-template-columns: 1fr; }} .ce-panel {{ border-left: 0; border-top: 1px solid #d7dde8; }} }}
  </style>
</head>
<body>
  <div class="ce-dashboard" data-ce-instance-workspace>
    <main class="ce-main">
      <p class="ce-notice">{escape(STANDALONE_LIMITATION)}</p>
      <section class="ce-overview">{global_html}</section>
      <section class="ce-workspace" data-workspace></section>
    </main>
    <aside class="ce-panel">
      <label for="ce-instance-select">Instance</label>
      <select id="ce-instance-select" data-instance-select></select>
      <dl class="ce-kv" data-summary></dl>
      <div class="ce-card-list" data-card-list></div>
    </aside>
  </div>
  <script type="application/json" id="ce-instance-workspace-data">{escape(payload_json)}</script>
  <script>
  (function () {{
    const data = JSON.parse(document.getElementById('ce-instance-workspace-data').textContent);
    const select = document.querySelector('[data-instance-select]');
    const summary = document.querySelector('[data-summary]');
    const cardList = document.querySelector('[data-card-list]');
    const workspace = document.querySelector('[data-workspace]');
    function fmt(value) {{ return value === null || value === undefined ? 'unavailable' : String(value); }}
    function renderSummary(record) {{
      const local = data.precomputed[String(record.instance_index)];
      const details = local ? local.summary : record;
      const rows = [
        ['instance index', record.instance_index],
        ['prediction', details.prediction],
        ['calibrated interval', '[' + fmt(details.low) + ', ' + fmt(details.high) + ']'],
        ['uncertainty', details.uncertainty || details.interval_width],
        ['task/posture', (details.task || record.metadata.task) + ' / ' + (details.posture || record.metadata.posture)],
        ['true label/target', details.true_label || details.target_value || details.target_label || details.target]
      ];
      // Values (labels, targets) are user-controlled data: always assign via
      // textContent, never innerHTML, so hostile strings render as text.
      summary.replaceChildren();
      rows.forEach(([k, v]) => {{
        const dt = document.createElement('dt');
        dt.textContent = String(k);
        const dd = document.createElement('dd');
        dd.textContent = fmt(v);
        summary.appendChild(dt);
        summary.appendChild(dd);
      }});
    }}
    function renderCards(instanceIndex) {{
      const local = data.precomputed[String(instanceIndex)];
      cardList.innerHTML = '';
      if (!local || !local.cards.length) {{
        cardList.innerHTML = '<p>No precomputed local cards are available for this instance.</p>';
        return;
      }}
      local.cards.forEach((card, position) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = card.available ? 'Add ' + card.label : card.label + ' unavailable';
        button.disabled = !card.available;
        button.addEventListener('click', function () {{
          const fragment = data.cardFragments[String(instanceIndex)][position];
          const wrap = document.createElement('div');
          wrap.innerHTML = fragment.html;
          workspace.appendChild(wrap.firstElementChild);
        }});
        cardList.appendChild(button);
      }});
    }}
    function selectInstance(instanceIndex) {{
      const record = data.records.find((item) => Number(item.instance_index) === Number(instanceIndex)) || data.records[0];
      if (!record) return;
      select.value = String(record.instance_index);
      renderSummary(record);
      renderCards(record.instance_index);
    }}
    data.records.forEach((record) => {{
      const option = document.createElement('option');
      option.value = String(record.instance_index);
      option.textContent = 'Instance ' + record.instance_index;
      select.appendChild(option);
    }});
    select.addEventListener('change', function () {{ selectInstance(select.value); }});
    document.addEventListener('click', function (event) {{
      if (event.target && event.target.matches('[data-card-remove]')) {{
        event.target.closest('.ce-workspace-card').remove();
      }}
    }});
    const overview = document.getElementById('ce-instance-overview');
    if (overview && overview.on) {{
      overview.on('plotly_click', function (event) {{
        const point = event.points && event.points[0];
        const marker = data.globalMarkers && data.globalMarkers[point.pointIndex];
        if (marker && marker.instance_indices && marker.instance_indices.length) {{
          selectInstance(marker.instance_indices[0]);
        }}
      }});
    }}
    selectInstance(data.records[0] && data.records[0].instance_index);
  }})();
  </script>
</body>
</html>"""


def _display_html(html_content: str) -> bool:
    try:
        from IPython.display import HTML, display
    except ImportError:
        return False
    display(HTML(html_content))
    return True


def export_html(artifact: PlotArtifact, path: str | Path) -> str:
    html_path = Path(path)
    if html_path.suffix.lower() != ".html":
        html_path = html_path.with_suffix(".html")
    html_path.write_text(build_dashboard_html(artifact), encoding="utf-8")
    return str(html_path)


class InstanceWorkspaceDashboardRenderer(PlotRenderer):
    """Render standalone instance-workspace dashboard artifacts as HTML."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": PACKAGE_VERSION,
        "provider": PROVIDER,
        "data_modalities": ("tabular",),
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": ("plotly",),
        "trusted": False,
        "trust": False,
        "supports_interactive": True,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        if artifact.get("artifact_type") != ARTIFACT_TYPE:
            raise ConfigurationError(
                "Unexpected artifact type for plotly.dashboard.instance_workspace."
            )
        html_content = build_dashboard_html(artifact)
        saved_paths: tuple[str, ...] = ()
        if context.path:
            saved_paths = (export_html(artifact, context.path),)
        if context.show:
            _display_html(html_content)
        global_figure = build_global_instance_explorer_figure(
            dict(artifact["global_artifact"]),
            dict(artifact.get("global_artifact", {}).get("options", {}) or {}),
        )
        return PlotRenderResult(
            artifact=artifact,
            figure=global_figure,
            saved_paths=saved_paths,
            extras={"html": html_content, "figure": global_figure},
        )


__all__ = [
    "ARTIFACT_TYPE",
    "ARTIFACT_VERSION",
    "BUILDER_ID",
    "RENDERER_ID",
    "STANDALONE_LIMITATION",
    "STYLE_ID",
    "InstanceWorkspaceDashboardBuilder",
    "InstanceWorkspaceDashboardRenderer",
    "build_dashboard_html",
    "export_html",
]
