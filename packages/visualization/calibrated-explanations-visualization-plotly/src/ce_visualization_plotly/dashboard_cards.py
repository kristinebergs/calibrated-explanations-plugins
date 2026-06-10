from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping

from .alternative_feature_summary import STYLE_ID as ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID
from .ensured import STYLE_ID as ENSURED_STYLE_ID
from .factual_bars import STYLE_ID as FACTUAL_BARS_STYLE_ID
from .instance_explorer import STYLE_ID as INSTANCE_EXPLORER_STYLE_ID
from .quadrant import STYLE_ID as UNCERTAINTY_QUADRANT_STYLE_ID

DashboardCardScope = Literal["global", "local"]


@dataclass(frozen=True)
class DashboardCardDescriptor:
    """Describe a Plotly plot card that can be rendered in a dashboard workspace."""

    card_id: str
    style: str
    label: str
    description: str
    scope: DashboardCardScope
    requires: tuple[str, ...]
    supports_tasks: tuple[str, ...]
    default_options: Mapping[str, Any]
    experimental: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "requires", tuple(self.requires))
        object.__setattr__(self, "supports_tasks", tuple(self.supports_tasks))
        object.__setattr__(
            self,
            "default_options",
            MappingProxyType(dict(self.default_options)),
        )

    def supports_task(self, task: str | None) -> bool:
        """Return whether this card supports a dashboard task label."""
        if task is None:
            return True
        return task in self.supports_tasks


_ALL_TASKS = (
    "classification",
    "probabilistic_regression",
    "conformal_regression",
    "regression",
)

_DASHBOARD_CARDS: tuple[DashboardCardDescriptor, ...] = (
    DashboardCardDescriptor(
        card_id="instance_explorer",
        style=INSTANCE_EXPLORER_STYLE_ID,
        label="Instance Explorer",
        description="Batch-level prediction and uncertainty overview with hover inspection.",
        scope="global",
        requires=("global_predictions",),
        supports_tasks=("auto", *_ALL_TASKS),
        default_options={
            "task": "auto",
            "aggregate_positions": True,
            "aggregation_strategy": "round",
            "position_precision": 3,
            "marker_size_mode": "count",
            "marker_size_min": 6,
            "marker_size_max": 32,
            "show_individual_points": False,
            "include_instance_records": False,
            "show_triangle_reference": True,
        },
    ),
    DashboardCardDescriptor(
        card_id="local_factual_bars",
        style=FACTUAL_BARS_STYLE_ID,
        label="Local Factual Bars",
        description="Local factual contribution bars with calibrated interval details in hover.",
        scope="local",
        requires=("factual_explanation",),
        supports_tasks=_ALL_TASKS,
        default_options={
            "show_uncertainty": False,
            "hover_uncertainty": True,
            "filter_top": 10,
        },
    ),
    DashboardCardDescriptor(
        card_id="uncertainty_quadrant",
        style=UNCERTAINTY_QUADRANT_STYLE_ID,
        label="Uncertainty Quadrant",
        description="Local factual feature-impact view that separates impact and interval width.",
        scope="local",
        requires=("factual_explanation", "prediction_interval"),
        supports_tasks=_ALL_TASKS,
        default_options={
            "threshold_strategy": "median",
            "sort_by": "absolute_impact",
            "filter_top": None,
        },
    ),
    DashboardCardDescriptor(
        card_id="ensured",
        style=ENSURED_STYLE_ID,
        label="Ensured Alternatives",
        description="Local alternative-rule plot showing prediction, uncertainty, and ensured roles.",
        scope="local",
        requires=("alternative_explanation", "prediction_interval"),
        supports_tasks=_ALL_TASKS,
        default_options={
            "sort_by": "rank",
            "filter_top": None,
            "show_arrows": True,
            "show_original": True,
            "show_triangle_reference": True,
            "hover_detail": "compact",
            "include_missing_rule_points": True,
            "feature_checklist": False,
            "side_panel": False,
        },
    ),
    DashboardCardDescriptor(
        card_id="alternative_feature_summary",
        style=ALTERNATIVE_FEATURE_SUMMARY_STYLE_ID,
        label="Alternative Feature Summary",
        description=(
            "Local alternative-rule summary grouped by feature, role, and quality flags."
        ),
        scope="local",
        requires=("alternative_explanation",),
        supports_tasks=_ALL_TASKS,
        default_options={
            "normalize": "count",
            "unknown_policy": "show",
            "sort_by": "total",
            "orientation": "horizontal",
            "hover_detail": "compact",
            "include_conjunctions": False,
            "filter_top_features": None,
            "infer_roles": False,
        },
    ),
)

_CARD_BY_ID = {descriptor.card_id: descriptor for descriptor in _DASHBOARD_CARDS}
_CARD_BY_STYLE = {descriptor.style: descriptor for descriptor in _DASHBOARD_CARDS}
_CARD_ALIASES = {
    "factual_bars": "local_factual_bars",
    "local_uncertainty_quadrant": "uncertainty_quadrant",
    "local_ensured": "ensured",
    "local_alternative_feature_summary": "alternative_feature_summary",
}


def iter_dashboard_cards() -> tuple[DashboardCardDescriptor, ...]:
    """Return all registered Plotly dashboard card descriptors in display order."""
    return _DASHBOARD_CARDS


def find_dashboard_card(card_id: str) -> DashboardCardDescriptor | None:
    """Find a dashboard card descriptor by stable card id."""
    return _CARD_BY_ID.get(_CARD_ALIASES.get(card_id, card_id))


def find_dashboard_card_by_style(style: str) -> DashboardCardDescriptor | None:
    """Find a dashboard card descriptor by CE Plotly style id."""
    return _CARD_BY_STYLE.get(style)


def dashboard_cards_for_scope(scope: DashboardCardScope) -> tuple[DashboardCardDescriptor, ...]:
    """Return cards available for a global or local dashboard area."""
    return tuple(descriptor for descriptor in _DASHBOARD_CARDS if descriptor.scope == scope)


def dashboard_cards_for_task(task: str | None) -> tuple[DashboardCardDescriptor, ...]:
    """Return cards that can be shown for the supplied task label."""
    return tuple(descriptor for descriptor in _DASHBOARD_CARDS if descriptor.supports_task(task))


__all__ = [
    "DashboardCardDescriptor",
    "DashboardCardScope",
    "dashboard_cards_for_scope",
    "dashboard_cards_for_task",
    "find_dashboard_card",
    "find_dashboard_card_by_style",
    "iter_dashboard_cards",
]
