"""Simple factual weight bars matching the explainable-ai-hub ExplainPage figure.

Replicates the client-side Plotly figure the hub builds next to the factual
rule list: one horizontal bar per rule (conjunctions included via CE's
``get_rules()``, which returns the merged conjunctive rules when present),
coloured by weight sign, with optional symmetric-style error bars for the
weight interval. Unlike ``plotly.local.factual_bars`` there is no prediction
header, no CE ranking, and no instance-value axis — rules are shown in payload
order with a fixed compact layout.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any

from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)

from .factual_bars import (
    _as_float,
    _is_alternative_explanation,
    _resolve_rules,
    _select_local_explanation,
    _sequence_get,
)

STYLE_ID = "plotly.local.factual_simple"
BUILDER_ID = "official.visualization.plotly.local.factual_simple.builder"
RENDERER_ID = "official.visualization.plotly.local.factual_simple.renderer"
ARTIFACT_VERSION = "0.1.0"

_LOGGER = logging.getLogger(__name__)

# Colors match the explainable-ai-hub CSS-variable fallbacks
# (--ce-weight-positive / --ce-weight-negative).
_POSITIVE_COLOR = "hsl(243,75%,59%)"
_NEGATIVE_COLOR = "hsl(0,84%,60%)"

# Rule labels longer than this are truncated to 30 characters plus an ellipsis,
# mirroring the hub's list rendering.
_MAX_LABEL_LENGTH = 32


def _warn_fallback(reason: str) -> None:
    message = f"Plotly factual simple fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _truncate_label(label: str) -> str:
    if len(label) > _MAX_LABEL_LENGTH:
        return label[:30] + "…"
    return label


def _default_options(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "show_uncertainty": bool(
            options.get("show_uncertainty", bool(options.get("uncertainty", False)))
        ),
    }


class LocalFactualSimplePlotBuilder(PlotBuilder):
    """Build a Plotly artifact for the hub-style simple factual weight bars."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
        "data_modalities": ("tabular",),
        "style": STYLE_ID,
        "intent": "factual",
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": (),
        "trusted": False,
        "trust": False,
        "legacy_compatible": False,
        "default_renderer": RENDERER_ID,
    }

    def build(self, context: PlotRenderContext) -> PlotArtifact:
        intent_type = context.intent.get("type")
        if intent_type not in (None, "factual"):
            raise ValueError(
                "plotly.local.factual_simple supports factual local explanations only."
            )

        options = _default_options(dict(context.options))
        local_explanation = _select_local_explanation(
            context.explanation,
            context.options.get("instance_index"),
        )
        if _is_alternative_explanation(local_explanation):
            raise ValueError(
                "plotly.local.factual_simple does not support alternative explanations."
            )

        rules = _resolve_rules(local_explanation)
        weights = list(rules.get("weight", ()))
        lows = list(rules.get("weight_low", rules.get("low", ())))
        highs = list(rules.get("weight_high", rules.get("high", ())))
        labels = list(rules.get("rule", ()))

        # Payload order preserved (rules then conjunctions), NaN/None weights skipped —
        # exactly the hub's ruleChartData construction.
        items: list[dict[str, Any]] = []
        for index, raw_weight in enumerate(weights):
            weight = _as_float(raw_weight)
            if weight is None or weight != weight:  # skip None and NaN
                continue
            low = _as_float(_sequence_get(lows, index))
            high = _as_float(_sequence_get(highs, index))
            condition = str(_sequence_get(labels, index, f"rule {index}"))
            items.append(
                {
                    "id": f"rule-{index}",
                    "rule": condition,
                    "name": _truncate_label(condition),
                    "weight": weight,
                    "error_low": max(0.0, weight - low) if low is not None else 0.0,
                    "error_high": max(0.0, high - weight) if high is not None else 0.0,
                    "direction": "positive" if weight >= 0.0 else "negative",
                    "metadata": {"original_index": index},
                }
            )

        if not items:
            raise ValueError("No factual rule contributions were available for plotting.")

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "items": items,
            "axis_metadata": {
                "x_label": "Weight",
                "zero_line": True,
            },
            "options_used": {
                "show_uncertainty": options["show_uncertainty"],
            },
            "metadata": {
                "num_items": len(items),
                "created_by": STYLE_ID,
                "instance_index": getattr(local_explanation, "index", None),
            },
        }


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    """Build the Plotly figure exactly as the explainable-ai-hub ExplainPage does."""
    import plotly.graph_objects as go  # noqa: PLC0415

    render_options = dict(artifact.get("options_used", {}) or {})
    render_options.update(options)
    show_uncertainty = bool(render_options.get("show_uncertainty", False))

    items = list(artifact.get("items", ()))
    axis_meta = dict(artifact.get("axis_metadata", {}) or {})

    trace_kwargs: dict[str, Any] = {
        "x": [item["weight"] for item in items],
        "y": [item["name"] for item in items],
        "orientation": "h",
        "marker": {
            "color": [
                _POSITIVE_COLOR if item["weight"] >= 0 else _NEGATIVE_COLOR for item in items
            ]
        },
        "hovertemplate": "%{y}<br>Weight: %{x:.4f}<extra></extra>",
    }
    if show_uncertainty:
        trace_kwargs["error_x"] = {
            "type": "data",
            "array": [item["error_high"] for item in items],
            "arrayminus": [item["error_low"] for item in items],
            "visible": True,
        }

    fig = go.Figure(data=[go.Bar(**trace_kwargs)])
    fig.update_layout(
        margin={"l": 10, "r": 20, "t": 10, "b": 40},
        xaxis={
            "title": axis_meta.get("x_label", "Weight"),
            "zeroline": bool(axis_meta.get("zero_line", True)),
            "zerolinewidth": 2,
        },
        yaxis={"automargin": True, "tickfont": {"size": 10}},
        height=max(320, len(items) * 40 + 80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


class LocalFactualSimplePlotRenderer(PlotRenderer):
    """Render simple factual bar artifacts as Plotly horizontal bar charts."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
        "data_modalities": ("tabular",),
        "output_formats": ("html",),
        "capabilities": ["plot:renderer"],
        "dependencies": ("plotly",),
        "trusted": False,
        "trust": False,
        "supports_interactive": True,
    }

    def render(self, artifact: PlotArtifact, *, context: PlotRenderContext) -> PlotRenderResult:
        if artifact.get("artifact_type") != STYLE_ID:
            _warn_fallback("received an unexpected artifact type; rendering with available fields.")
        try:
            figure = build_figure(artifact, dict(context.options))
        except ImportError as exc:
            raise RuntimeError(
                "Plotly is required to render plotly.local.factual_simple. "
                "Install plotly (a mandatory dependency of "
                "calibrated-explanations-visualization-plotly); your "
                "environment appears to be missing or shadowing it."
            ) from exc

        saved_paths: tuple[str, ...] = ()
        if context.path:
            html_path = Path(context.path)
            if html_path.suffix.lower() != ".html":
                html_path = html_path.with_suffix(".html")
            figure.write_html(
                str(html_path),
                config={"responsive": True, "displayModeBar": "hover"},
            )
            saved_paths = (str(html_path),)
        if context.show:
            figure.show()
        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={"figure": figure},
        )


__all__ = [
    "STYLE_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "ARTIFACT_VERSION",
    "LocalFactualSimplePlotBuilder",
    "LocalFactualSimplePlotRenderer",
    "build_figure",
]
