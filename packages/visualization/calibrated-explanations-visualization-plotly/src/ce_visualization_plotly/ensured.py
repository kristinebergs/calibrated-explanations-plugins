from __future__ import annotations

import json
import logging
import warnings
from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)
from calibrated_explanations.utils.helper import calculate_metrics
from calibrated_explanations.viz.builders import build_triangular_plotspec

STYLE_ID = "plotly.local.ensured"
ALIAS_STYLE_ID = "plotly.local.ensured_triangular"
BUILDER_ID = "official.visualization.plotly.local.ensured.builder"
RENDERER_ID = "official.visualization.plotly.local.ensured.renderer"
ARTIFACT_VERSION = "0.2.0"

_LOGGER = logging.getLogger(__name__)
_ORIGINAL_POINT_ID = "original-point"
_RULE_FALLBACK = "Rule condition unavailable"
_ORIGINAL_COLOR = "#d62728"
_RULE_COLOR = "#1f77b4"
_ARROW_COLOR = "rgba(110, 110, 110, 0.75)"
_EMPTY_PANEL_TITLE = "Rule details"
_EMPTY_PANEL_BODY = "Click a rule point to inspect the selected rule and feature details."


def _warn_fallback(reason: str) -> None:
    message = f"Plotly ensured fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _warn_deprecated_alias(style_id: str) -> None:
    if style_id != ALIAS_STYLE_ID:
        return
    message = (
        "plotly.local.ensured_triangular is deprecated; use plotly.local.ensured instead."
    )
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sequence_get(values: Any, index: int, default: Any = None) -> Any:
    if values is None:
        return default
    try:
        return values[index]
    except (IndexError, KeyError, TypeError):
        return default


def _serialise_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_serialise_value(item) for item in value]
    return value


def _display_value(value: Any) -> str:
    serialised = _serialise_value(value)
    if isinstance(serialised, list):
        return ", ".join(str(item) for item in serialised)
    return str(serialised)


def _collection_for(explanation: Any) -> Any:
    return getattr(explanation, "calibrated_explanations", explanation)


def _select_local_explanation(explanation: Any, instance_index: int | None) -> Any:
    explanations = getattr(explanation, "explanations", None)
    if explanations is None:
        return explanation
    if len(explanations) == 0:
        raise ValueError("No explanations are available for plotting.")
    selected = 0 if instance_index is None else int(instance_index)
    return explanations[selected]


def _is_alternative_explanation(local_explanation: Any) -> bool:
    sentinel = object()
    is_alternative = getattr(local_explanation, "is_alternative", sentinel)
    if callable(is_alternative):
        return bool(is_alternative())
    if isinstance(is_alternative, bool):
        return is_alternative
    class_name = type(local_explanation).__name__.lower()
    if "alternative" in class_name:
        return True
    get_rules = getattr(local_explanation, "get_rules", None)
    return callable(get_rules) and hasattr(local_explanation, "prediction")


def _feature_name(collection: Any, feature: Any) -> str | None:
    names = getattr(collection, "feature_names", None)
    if callable(names):
        names = names()
    index = _as_float(feature)
    if names is not None and index is not None and index.is_integer():
        try:
            return str(names[int(index)])
        except (IndexError, TypeError):
            return None
    if feature is None:
        return None
    return str(feature)


def _conjunction_size(feature: Any, rule: str, is_conjunctive: bool) -> int:
    if isinstance(feature, np.ndarray):
        return max(1, int(feature.size))
    if isinstance(feature, (list, tuple, set)):
        return max(1, len(feature))
    if not is_conjunctive:
        return 1
    normalised_rule = str(rule or "").replace("& \n", " AND ").replace("\n", " ")
    if " AND " in normalised_rule:
        return max(1, len([part for part in normalised_rule.split(" AND ") if part.strip()]))
    if " & " in normalised_rule:
        return max(1, len([part for part in normalised_rule.split(" & ") if part.strip()]))
    return 2


def _marker_size_for_conjunction(
    point: dict[str, Any],
    options: dict[str, Any],
    max_conjunction_size: int,
) -> float:
    minimum = float(options.get("conjunction_marker_size_min", 9))
    maximum = float(options.get("conjunction_marker_size_max", 14))
    size = int(point.get("conjunction_size", point.get("metadata", {}).get("conjunction_size", 1)))
    if maximum <= minimum or max_conjunction_size <= 1 or size <= 1:
        return minimum
    scale = (min(size, max_conjunction_size) - 1) / (max_conjunction_size - 1)
    return minimum + scale * (maximum - minimum)


def _mode_metadata(explanation: Any, local_explanation: Any) -> dict[str, Any]:
    batch_metadata = dict(getattr(explanation, "batch_metadata", {}) or {})
    get_mode = getattr(local_explanation, "get_mode", None)
    raw_mode = get_mode() if callable(get_mode) else batch_metadata.get("mode")
    is_regression = bool(getattr(local_explanation, "is_regression", lambda: False)())
    is_probabilistic = bool(getattr(local_explanation, "is_probabilistic", lambda: False)())
    task = batch_metadata.get("task")
    if task is None:
        task = "regression" if is_regression else "classification" if is_probabilistic else raw_mode
    mode = raw_mode or task
    return {
        "task": task,
        "mode": mode,
        "is_regression": is_regression,
        "is_probabilistic": is_probabilistic,
    }


def _resolve_alternative_rules(local_explanation: Any) -> dict[str, Any]:
    if getattr(local_explanation, "has_conjunctive_rules", False) and getattr(
        local_explanation, "conjunctive_rules", None
    ):
        rules = local_explanation.conjunctive_rules
    else:
        get_rules = getattr(local_explanation, "get_rules", None)
        rules = get_rules() if callable(get_rules) else getattr(local_explanation, "rules", None)
    if not isinstance(rules, Mapping):
        raise ValueError("The explanation does not expose alternative-rule data.")
    return dict(rules)


def _finite_interval(
    low: float | None,
    high: float | None,
    y_minmax: Any,
) -> tuple[float | None, float | None]:
    if low is None or high is None:
        return low, high
    if y_minmax is None:
        return low, high
    try:
        min_y = float(y_minmax[0])
        max_y = float(y_minmax[1])
    except (TypeError, ValueError, IndexError):
        return low, high
    if np.isneginf(low):
        low = min_y
    if np.isposinf(high):
        high = max_y
    return low, high


def _ranked_rule_indices(
    local_explanation: Any,
    rules: dict[str, Any],
    prediction: dict[str, Any],
) -> list[int]:
    num_rules = len(list(rules.get("rule", ())))
    if num_rules == 0:
        return []

    predict_values = list(rules.get("predict", ()))
    low_values = list(rules.get("predict_low", ()))
    high_values = list(rules.get("predict_high", ()))
    uncertainties = [
        float(high_values[index]) - float(low_values[index]) for index in range(num_rules)
    ]
    ranking_prediction = list(predict_values)
    base_prediction = float(prediction.get("predict", 0.0))
    is_thresholded = bool(getattr(local_explanation, "is_thresholded", lambda: False)())
    if local_explanation.get_mode() == "classification" or is_thresholded:
        ranking_prediction = [
            float(value) if base_prediction > 0.5 else 1.0 - float(value)
            for value in predict_values
        ]

    ranking = calculate_metrics(
        uncertainty=uncertainties,
        prediction=ranking_prediction,
        w=0.5,
        metric="ensured",
    )
    rank_features = getattr(local_explanation, "rank_features", None)
    if callable(rank_features):
        ordered = rank_features(width=ranking, num_to_show=num_rules)
    else:
        _warn_fallback("rank_features unavailable; using deterministic argsort for rank ordering.")
        ordered = sorted(range(num_rules), key=lambda index: (ranking[index], index))

    ordered_indices = list(reversed([int(index) for index in ordered]))
    filtered_indices: list[int] = []
    for index in ordered_indices:
        if np.isclose(float(predict_values[index]), base_prediction) and np.isclose(
            float(low_values[index]), float(prediction.get("low", 0.0))
        ) and np.isclose(float(high_values[index]), float(prediction.get("high", 0.0))):
            continue
        filtered_indices.append(index)
    return filtered_indices


def _axis_range(
    values: list[float], *, default: tuple[float, float], include_zero: bool = False
) -> list[float]:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    if not finite:
        return [float(default[0]), float(default[1])]
    min_value = min(finite)
    max_value = max(finite)
    if include_zero:
        min_value = min(min_value, 0.0)
        max_value = max(max_value, 0.0)
    if np.isclose(min_value, max_value):
        padding = abs(min_value) * 0.1 or 0.1
        return [min_value - padding, max_value + padding]
    padding = (max_value - min_value) * 0.08
    return [min_value - padding, max_value + padding]


def _triangle_reference_metadata(is_probabilistic: bool) -> dict[str, Any]:
    if is_probabilistic:
        return {
            "enabled": True,
            "kind": "probability_triangle",
            "description": "Probability triangle reference region for alternative predictions.",
        }
    return {
        "enabled": False,
        "kind": "none",
        "description": "Triangle reference is disabled outside probabilistic mode.",
    }


def _resolve_role_priority(flags: dict[str, bool]) -> str:
    for role in (
        "ensured",
        "pareto",
        "counterfactual",
        "counterpotential",
        "semifactual",
    ):
        if flags.get(role, False):
            return role
    return "unknown"


def _rule_identity_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return tuple(_rule_identity_value(item) for item in value.ravel().tolist())
    if isinstance(value, (list, tuple)):
        return tuple(_rule_identity_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _rule_identity_value(item)) for key, item in value.items()))
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _rule_numeric_identity_value(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float):
        return round(value, 12)
    return _rule_identity_value(value)


def _rule_feature_identity_value(value: Any) -> Any:
    normalised = _rule_identity_value(value)
    if isinstance(normalised, tuple):
        return tuple(sorted(normalised, key=repr))
    return normalised


def _rule_identity(rules: dict[str, Any], rule_index: int) -> tuple[Any, ...]:
    return tuple(
        _rule_identity_value(_sequence_get(rules.get(key, ()), rule_index))
        for key in ("rule", "feature", "predict", "predict_low", "predict_high")
    )


def _rule_relaxed_identity(rules: dict[str, Any], rule_index: int) -> tuple[Any, ...]:
    return (
        _rule_feature_identity_value(_sequence_get(rules.get("feature", ()), rule_index)),
        _rule_numeric_identity_value(_sequence_get(rules.get("predict", ()), rule_index)),
        _rule_numeric_identity_value(_sequence_get(rules.get("predict_low", ()), rule_index)),
        _rule_numeric_identity_value(_sequence_get(rules.get("predict_high", ()), rule_index)),
        _rule_identity_value(_sequence_get(rules.get("is_conjunctive", ()), rule_index)),
    )


def _rule_indexes_matching_filtered_rules(
    original_rules: dict[str, Any],
    filtered_rules: dict[str, Any],
) -> set[int]:
    filtered_strict_identities = {
        _rule_identity(filtered_rules, index)
        for index in range(len(filtered_rules.get("rule", ())))
    }
    filtered_relaxed_identities = {
        _rule_relaxed_identity(filtered_rules, index)
        for index in range(len(filtered_rules.get("rule", ())))
    }
    return {
        index
        for index in range(len(original_rules.get("rule", ())))
        if _rule_identity(original_rules, index) in filtered_strict_identities
        or _rule_relaxed_identity(original_rules, index) in filtered_relaxed_identities
    }


def _filtered_rules_from_role_method(
    local_explanation: Any,
    role_name: str,
    options: dict[str, Any],
) -> dict[str, Any] | None:
    method_names = {
        "ensured": ("ensured", "ensured_explanations"),
        "pareto": ("pareto", "pareto_explanations"),
        "counterfactual": ("counter", "counter_explanations"),
        "counterpotential": ("super", "super_explanations"),
        "semifactual": ("semi", "semi_explanations"),
    }
    for method_name in method_names[role_name]:
        method = getattr(local_explanation, method_name, None)
        if not callable(method):
            continue
        try:
            if role_name == "pareto":
                filtered = method(
                    include_potential=True,
                    copy=True,
                    pareto_cost=str(options.get("pareto_cost", "uncertainty_width")),
                )
            elif role_name == "ensured":
                filtered = method(include_potential=True, copy=True)
            else:
                filtered = method(
                    only_ensured=False,
                    include_potential=True,
                    copy=True,
                )
        except TypeError:
            continue
        try:
            filtered_rules = _resolve_alternative_rules(filtered)
        except ValueError:
            continue
        if filtered_rules:
            return filtered_rules
    return None


def _resolve_role_memberships(
    local_explanation: Any,
    rules: dict[str, Any],
    options: dict[str, Any],
) -> tuple[dict[str, set[int]], set[str]]:
    memberships: dict[str, set[int]] = {}
    available_roles: set[str] = set()
    for role_name in (
        "ensured",
        "pareto",
        "counterfactual",
        "counterpotential",
        "semifactual",
    ):
        filtered_rules = _filtered_rules_from_role_method(local_explanation, role_name, options)
        if filtered_rules is None:
            continue
        memberships[role_name] = _rule_indexes_matching_filtered_rules(rules, filtered_rules)
        available_roles.add(role_name)
    return memberships, available_roles


def _role_source_from_flags(source_hits: dict[str, bool], heuristic_used: bool) -> str:
    if source_hits.get("ce_metadata"):
        return "ce_metadata"
    if source_hits.get("rule_metadata"):
        return "rule_metadata"
    if heuristic_used:
        return "heuristic"
    return "unavailable"


def _resolve_rule_role(
    *,
    local_explanation: Any,
    rules: dict[str, Any],
    rule_index: int,
    original: dict[str, Any],
    point_prediction: float,
    point_uncertainty: float,
    mode_metadata: dict[str, Any],
    role_memberships: dict[str, set[int]] | None = None,
    role_membership_sources: set[str] | None = None,
) -> dict[str, Any]:
    flags = {
        "counterfactual": False,
        "counterpotential": False,
        "semifactual": False,
        "ensured": False,
        "pareto": False,
    }
    source_hits = {
        "ce_metadata": False,
        "rule_metadata": False,
    }
    heuristic_used = False

    membership_sources = set(role_membership_sources or ())
    if membership_sources:
        for role_name in flags:
            if role_name in membership_sources:
                flags[role_name] = rule_index in (role_memberships or {}).get(role_name, set())
        source_hits["ce_metadata"] = True

    rule_key_map = {
        "counterfactual": ("is_counterfactual", "counterfactual"),
        "counterpotential": ("is_counterpotential", "counterpotential"),
        "semifactual": ("is_semifactual", "semifactual"),
        "ensured": ("is_ensured", "ensured"),
        "pareto": ("is_pareto", "pareto"),
    }
    for role_name, candidate_keys in rule_key_map.items():
        if role_name in membership_sources:
            continue
        for candidate_key in candidate_keys:
            values = rules.get(candidate_key)
            if values is None:
                continue
            candidate_value = _sequence_get(values, rule_index)
            if isinstance(candidate_value, (bool, np.bool_)):
                flags[role_name] = bool(candidate_value)
                source_hits["rule_metadata"] = True
                break

    if not any(flags.values()) and not membership_sources:
        if point_uncertainty <= original["uncertainty"] + 1e-12:
            flags["ensured"] = True
            heuristic_used = True

        boundary = None
        if mode_metadata["is_probabilistic"]:
            boundary = 0.5
            if bool(getattr(local_explanation, "is_thresholded", lambda: False)()):
                threshold_value = getattr(local_explanation, "y_threshold", None)
                candidate_threshold = _as_float(threshold_value)
                if candidate_threshold is not None:
                    boundary = candidate_threshold
        if boundary is not None:
            original_positive = original["prediction"] >= boundary
            point_positive = point_prediction >= boundary
            if original_positive != point_positive:
                flags["counterfactual"] = True
                heuristic_used = True

    explanation_role = _resolve_role_priority(flags)
    role_source = _role_source_from_flags(source_hits, heuristic_used)
    role_confidence = 0.0
    if role_source == "rule_metadata":
        role_confidence = 1.0
    elif explanation_role == "ensured":
        role_confidence = 0.85
    elif explanation_role == "counterfactual":
        role_confidence = 0.7

    return {
        "explanation_role": explanation_role,
        "is_counterfactual": flags["counterfactual"],
        "is_counterpotential": flags["counterpotential"],
        "is_semifactual": flags["semifactual"],
        "is_ensured": flags["ensured"],
        "is_pareto": flags["pareto"],
        "role_confidence": role_confidence,
        "role_source": role_source,
    }


def build_hover_text(item: dict[str, Any], options: dict[str, Any]) -> str:
    detail = str(options.get("hover_detail", "compact"))
    kind = item.get("kind", "rule")
    if kind == "original":
        lines = ["Original prediction"]
        lines.append(f"Prediction: {item['prediction']:.6g}")
        lines.append(f"Uncertainty: {item['uncertainty']:.6g}")
        if item.get("low") is not None and item.get("high") is not None:
            lines.append(f"Interval: [{item['low']:.6g}, {item['high']:.6g}]")
        return "<br>".join(lines)

    lines = [f"Rule: {item['rule']}"]
    lines.append(f"Conjunction size: {int(item.get('conjunction_size', 1))}")
    lines.append(f"Prediction: {item['prediction']:.6g}")
    lines.append(f"Uncertainty: {item['uncertainty']:.6g}")
    if item.get("low") is not None and item.get("high") is not None:
        lines.append(f"Interval: [{item['low']:.6g}, {item['high']:.6g}]")
    if detail == "full":
        if item.get("feature_name"):
            lines.append(f"Feature: {item['feature_name']}")
        if item.get("feature_index") is not None:
            lines.append(f"Feature index: {item['feature_index']}")
        if item.get("instance_value") is not None:
            lines.append(f"Instance value: {_display_value(item['instance_value'])}")
        if item.get("alternative_value") is not None:
            lines.append(f"Alternative value: {_display_value(item['alternative_value'])}")
        lines.append(f"Delta prediction: {item['delta_prediction']:+.6g}")
        lines.append(f"Delta uncertainty: {item['delta_uncertainty']:+.6g}")
        lines.append(f"Rank: {item['rank']}")
        lines.append(f"Role: {item['explanation_role']}")
        lines.append(f"Role source: {item['role_source']}")
    return "<br>".join(lines)


def _sort_rule_points(rule_points: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by == "rank":
        return sorted(rule_points, key=lambda item: (item["rank"], item["index"]))
    if sort_by == "uncertainty":
        return sorted(rule_points, key=lambda item: (-item["uncertainty"], item["index"]))
    if sort_by == "delta_prediction":
        return sorted(rule_points, key=lambda item: (-abs(item["delta_prediction"]), item["index"]))
    if sort_by == "delta_uncertainty":
        return sorted(rule_points, key=lambda item: (-abs(item["delta_uncertainty"]), item["index"]))
    if sort_by == "label":
        return sorted(rule_points, key=lambda item: (item["rule"].lower(), item["index"]))
    raise ValueError(
        "sort_by must be one of uncertainty, delta_prediction, delta_uncertainty, rank, or label."
    )


def _rule_groups(rule_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for point in rule_points:
        group_key = str(point.get("feature_name") or point.get("feature_index") or "unknown")
        group = groups.setdefault(
            group_key,
            {
                "group_key": group_key,
                "group_label": point.get("feature_name") or f"Feature {point.get('feature_index')}",
                "feature_index": point.get("feature_index"),
                "feature_name": point.get("feature_name"),
                "point_ids": [],
                "point_count": 0,
                "group_rank": point.get("rank", 0),
            },
        )
        group["point_ids"].append(point["id"])
        group["point_count"] += 1
        group["group_rank"] = min(int(group["group_rank"]), int(point.get("rank", group["group_rank"])))
    return sorted(
        groups.values(),
        key=lambda item: (int(item.get("group_rank", 0)), str(item.get("group_label") or item.get("group_key"))),
    )


class LocalEnsuredPlotBuilder(PlotBuilder):
    """Build a Plotly artifact for CE's ensured local alternative plot."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
        "style": STYLE_ID,
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
        if intent_type not in (None, "alternative"):
            raise ValueError("plotly.local.ensured supports alternative local explanations only.")

        deprecated_alias_used = context.style == ALIAS_STYLE_ID
        if deprecated_alias_used:
            _warn_deprecated_alias(context.style)

        options = dict(context.options)
        instance_index = options.get("instance_index")
        local_explanation = _select_local_explanation(context.explanation, instance_index)
        if not _is_alternative_explanation(local_explanation):
            raise ValueError("plotly.local.ensured requires an alternative explanation.")

        rules = _resolve_alternative_rules(local_explanation)
        prediction = dict(getattr(local_explanation, "prediction", {}) or {})
        y_minmax = getattr(local_explanation, "y_minmax", None)
        original_low, original_high = _finite_interval(
            _as_float(prediction.get("low")),
            _as_float(prediction.get("high")),
            y_minmax,
        )
        if original_low is None or original_high is None:
            raise ValueError("Alternative explanation is missing calibrated prediction intervals.")

        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        base_prediction = _as_float(prediction.get("predict"))
        if base_prediction is None:
            raise ValueError("Alternative explanation is missing a base prediction.")
        original = {
            "id": _ORIGINAL_POINT_ID,
            "kind": "original",
            "prediction": base_prediction,
            "uncertainty": float(original_high - original_low),
            "low": original_low,
            "high": original_high,
            "label": "Original Prediction",
        }
        original["hover"] = build_hover_text(original, options)

        default_rank_order = _ranked_rule_indices(local_explanation, rules, prediction)
        rank_by_index = {rule_index: rank + 1 for rank, rule_index in enumerate(default_rank_order)}
        role_memberships, role_membership_sources = _resolve_role_memberships(
            local_explanation,
            rules,
            options,
        )

        collection = _collection_for(local_explanation)
        rule_points: list[dict[str, Any]] = []
        missing_rule_metadata_count = 0
        missing_role_metadata_count = 0
        predict_values = list(rules.get("predict", ()))
        low_values = list(rules.get("predict_low", ()))
        high_values = list(rules.get("predict_high", ()))
        feature_values = list(rules.get("feature_value", ()))
        value_values = list(rules.get("value", ()))
        feature_indices = list(rules.get("feature", ()))
        rule_labels = list(rules.get("rule", ()))
        sampled_values = list(rules.get("sampled_values", ()))
        conjunctive_values = list(rules.get("is_conjunctive", ()))

        include_missing_rule_points = bool(options.get("include_missing_rule_points", True))

        for rule_index in default_rank_order:
            point_low, point_high = _finite_interval(
                _as_float(_sequence_get(low_values, rule_index)),
                _as_float(_sequence_get(high_values, rule_index)),
                y_minmax,
            )
            point_prediction = _as_float(_sequence_get(predict_values, rule_index))
            if point_prediction is None or point_low is None or point_high is None:
                continue

            raw_rule = _sequence_get(rule_labels, rule_index)
            has_rule_metadata = bool(str(raw_rule).strip()) if raw_rule is not None else False
            if not has_rule_metadata:
                missing_rule_metadata_count += 1
                if not include_missing_rule_points:
                    continue
            rule_condition = str(raw_rule).strip() if has_rule_metadata else _RULE_FALLBACK

            feature_index = _sequence_get(feature_indices, rule_index)
            feature_name = _feature_name(collection, feature_index)
            true_value = _serialise_value(
                _sequence_get(feature_values, rule_index, _sequence_get(value_values, rule_index))
            )
            alternative_value = _serialise_value(_sequence_get(sampled_values, rule_index))
            uncertainty = float(point_high - point_low)
            role_metadata = _resolve_rule_role(
                local_explanation=local_explanation,
                rules=rules,
                rule_index=rule_index,
                original=original,
                point_prediction=float(point_prediction),
                point_uncertainty=uncertainty,
                mode_metadata=mode_metadata,
                role_memberships=role_memberships,
                role_membership_sources=role_membership_sources,
            )
            if role_metadata["role_source"] == "unavailable":
                missing_role_metadata_count += 1

            is_conjunctive = bool(_sequence_get(conjunctive_values, rule_index, False))
            conjunction_size = _conjunction_size(feature_index, rule_condition, is_conjunctive)
            point = {
                "id": f"rule-point-{rule_index}",
                "kind": "rule",
                "index": int(rule_index),
                "feature_index": feature_index,
                "feature_name": feature_name,
                "true_value": true_value,
                "instance_value": true_value,
                "rule": rule_condition,
                "alternative_value": alternative_value,
                "prediction": float(point_prediction),
                "uncertainty": uncertainty,
                "low": float(point_low),
                "high": float(point_high),
                "delta_prediction": float(point_prediction - original["prediction"]),
                "delta_uncertainty": float(uncertainty - original["uncertainty"]),
                "rank": rank_by_index[rule_index],
                "is_conjunctive": is_conjunctive,
                "conjunction_size": conjunction_size,
                "metadata": {
                    "group_key": feature_name or str(feature_index) if feature_index is not None else "unknown",
                    "group_label": feature_name or f"Feature {feature_index}"
                    if feature_index is not None
                    else "Unknown feature",
                    "is_conjunctive": is_conjunctive,
                    "conjunction_size": conjunction_size,
                    "rule_metadata_missing": not has_rule_metadata,
                },
                **role_metadata,
            }
            point["hover"] = build_hover_text(point, options)
            rule_points.append(point)

        total_rule_count = len(rule_points)
        sort_by = str(options.get("sort_by", "rank"))
        sorted_rule_points = _sort_rule_points(rule_points, sort_by)

        filter_top = options.get("filter_top")
        if filter_top is None:
            filter_top = options.get("max_points")
        resolved_filter_top = None if filter_top is None else max(0, int(filter_top))
        shown_rule_points = (
            sorted_rule_points if resolved_filter_top is None else sorted_rule_points[:resolved_filter_top]
        )

        base_spec = build_triangular_plotspec(
            title="Alternative Explanations",
            proba=original["prediction"],
            uncertainty=original["uncertainty"],
            rule_proba=[point["prediction"] for point in shown_rule_points],
            rule_uncertainty=[point["uncertainty"] for point in shown_rule_points],
            num_to_show=len(shown_rule_points),
            is_probabilistic=bool(mode_metadata["is_probabilistic"]),
        )

        arrows = [
            {
                "id": f"arrow-original-to-{point['id']}",
                "from_point_id": _ORIGINAL_POINT_ID,
                "to_point_id": point["id"],
                "feature_key": point["metadata"]["group_key"],
                "x0": original["prediction"],
                "y0": original["uncertainty"],
                "x1": point["prediction"],
                "y1": point["uncertainty"],
                "delta_prediction": point["delta_prediction"],
                "delta_uncertainty": point["delta_uncertainty"],
                "roles": _rule_point_roles(point),
                "metadata": {
                    "feature_name": point.get("feature_name"),
                    "feature_index": point.get("feature_index"),
                    "rule": point.get("rule"),
                },
            }
            for point in shown_rule_points
        ]

        x_values = [original["prediction"], *[point["prediction"] for point in shown_rule_points]]
        y_values = [original["uncertainty"], *[point["uncertainty"] for point in shown_rule_points]]
        is_probabilistic = bool(mode_metadata["is_probabilistic"])
        axis_metadata = {
            "x_label": "Probability" if is_probabilistic else "Prediction",
            "y_label": "Uncertainty",
            "x_range": [0.0, 1.0]
            if is_probabilistic
            else _axis_range(x_values, default=(0.0, 1.0)),
            "y_range": [0.0, 1.0]
            if is_probabilistic
            else _axis_range(y_values, default=(0.0, 1.0), include_zero=True),
            "mode": mode_metadata["mode"],
        }
        feature_groups = _rule_groups(shown_rule_points)

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "base_plotspec_kind": base_spec.kind,
            "mode": mode_metadata["mode"],
            "task": mode_metadata["task"],
            "original": original,
            "rule_points": shown_rule_points,
            "arrows": arrows,
            "axis_metadata": axis_metadata,
            "triangle_reference_metadata": _triangle_reference_metadata(is_probabilistic),
            "interaction_capabilities": {
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
            },
            "options_used": {
                "filter_top": resolved_filter_top,
                "sort_by": sort_by,
                "show_arrows": bool(options.get("show_arrows", True)),
                "show_original": bool(options.get("show_original", True)),
                "show_triangle_reference": bool(options.get("show_triangle_reference", True)),
                "hover_detail": str(options.get("hover_detail", "compact")),
                "include_missing_rule_points": include_missing_rule_points,
                "feature_checklist": bool(options.get("feature_checklist", False)),
                "side_panel": bool(options.get("side_panel", False)),
            },
            "metadata": {
                "shown_rule_count": len(shown_rule_points),
                "total_rule_count": total_rule_count,
                "feature_count": len(feature_groups),
                "missing_rule_metadata_count": missing_rule_metadata_count,
                "missing_role_metadata_count": missing_role_metadata_count,
                "created_by": STYLE_ID,
                "deprecated_alias_used": deprecated_alias_used,
                "feature_groups": feature_groups,
            },
        }


def _trace_count(fig: Any) -> int:
    if hasattr(fig, "data"):
        return len(fig.data)
    return len(getattr(fig, "traces", ()))


def _add_trace(fig: Any, trace: Any, *, side_panel: bool, panel: str = "plot") -> None:
    del side_panel, panel
    fig.add_trace(trace)


def add_triangle_reference(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> list[int]:
    if not bool(options.get("show_triangle_reference", True)):
        return []
    metadata = dict(artifact.get("triangle_reference_metadata", {}) or {})
    if not metadata.get("enabled"):
        return []

    import plotly.graph_objects as go

    side_panel = bool(options.get("side_panel", False))
    trace_indexes: list[int] = []
    left_y = np.arange(0.0, 1.0, 0.01)
    left_x = left_y / (1.0 + left_y)
    right_x = np.arange(0.5, 1.0, 0.01)
    right_y = (1.0 - right_x) / right_x
    upper_y = np.arange(0.5, 1.0, 0.005)
    upper_x = upper_y / (upper_y + 0.5)
    lower_y = np.arange(0.0, 0.5, 0.005)
    lower_x = 0.5 / (1.0 + lower_y)

    for index, (xs, ys) in enumerate(
        ((left_x, left_y), (right_x, right_y), (upper_x, upper_y - 0.5), (lower_x, lower_y)),
        start=1,
    ):
        _add_trace(
            fig,
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="lines",
                line={"color": "#2f2f2f", "width": 1},
                hoverinfo="skip",
                meta={"trace_kind": "triangle-reference"},
                name=f"triangle-reference-{index}",
                showlegend=False,
            ),
            side_panel=side_panel,
        )
        trace_indexes.append(_trace_count(fig) - 1)
    return trace_indexes


def add_original_point(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> int | None:
    if not bool(options.get("show_original", True)):
        return None

    import plotly.graph_objects as go

    side_panel = bool(options.get("side_panel", False))
    original = dict(artifact.get("original", {}) or {})
    _add_trace(
        fig,
        go.Scatter(
            x=[original.get("prediction")],
            y=[original.get("uncertainty")],
            mode="markers",
            marker={"size": 12, "color": _ORIGINAL_COLOR},
            text=[original.get("hover")],
            hovertemplate="%{text}<extra></extra>",
            meta={"trace_kind": "original"},
            name="original",
        ),
        side_panel=side_panel,
    )
    return _trace_count(fig) - 1


def _rule_point_roles(point: dict[str, Any]) -> dict[str, bool]:
    return {
        "ensured": bool(point.get("is_ensured", False)),
        "pareto": bool(point.get("is_pareto", False)),
        "counter": bool(point.get("is_counterfactual", False)),
        "semi": bool(point.get("is_semifactual", False)),
        "super": bool(point.get("is_counterpotential", False)),
    }


def _role_signature(point: dict[str, Any]) -> tuple[bool, bool, bool, bool, bool]:
    roles = _rule_point_roles(point)
    return (
        roles["ensured"],
        roles["pareto"],
        roles["counter"],
        roles["semi"],
        roles["super"],
    )


def add_rule_points(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> dict[str, list[int]]:
    import plotly.graph_objects as go

    side_panel = bool(options.get("side_panel", False))
    feature_groups = dict(
        (group["group_key"], []) for group in artifact.get("metadata", {}).get("feature_groups", [])
    )
    for point in artifact.get("rule_points", ()): 
        feature_groups.setdefault(point["metadata"]["group_key"], []).append(point)

    trace_indexes: dict[str, list[int]] = {}
    show_feature_legend = bool(options.get("feature_checklist", False))
    for feature_key, points in feature_groups.items():
        if not points:
            continue
        feature_label = points[0].get("feature_name") or f"Feature {points[0].get('feature_index')}"
        max_conjunction_size = max(
            int(point.get("conjunction_size", point.get("metadata", {}).get("conjunction_size", 1)))
            for point in artifact.get("rule_points", ())
        )
        grouped_points: dict[tuple[bool, bool, bool, bool, bool], list[dict[str, Any]]] = {}
        for point in points:
            grouped_points.setdefault(_role_signature(point), []).append(point)

        trace_indexes[feature_key] = []
        for role_index, role_points in enumerate(grouped_points.values()):
            _add_trace(
                fig,
                go.Scatter(
                    x=[point.get("prediction") for point in role_points],
                    y=[point.get("uncertainty") for point in role_points],
                    mode="markers",
                    marker={
                        "size": [
                            _marker_size_for_conjunction(point, options, max_conjunction_size)
                            for point in role_points
                        ],
                        "color": _RULE_COLOR,
                    },
                    text=[point.get("hover") for point in role_points],
                    customdata=[point.get("id") for point in role_points],
                    hovertemplate="%{text}<extra></extra>",
                    meta={
                        "trace_kind": "rule-points",
                        "feature_key": feature_key,
                        "roles": _rule_point_roles(role_points[0]),
                    },
                    legendgroup=feature_key,
                    name=feature_label if show_feature_legend else "alternatives",
                    showlegend=show_feature_legend and role_index == 0,
                ),
                side_panel=side_panel,
            )
            trace_indexes[feature_key].append(_trace_count(fig) - 1)
    return trace_indexes


def add_arrows(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> dict[str, list[int]]:
    if not bool(options.get("show_arrows", True)):
        return {}

    import plotly.graph_objects as go

    side_panel = bool(options.get("side_panel", False))
    feature_checklist = bool(options.get("feature_checklist", False))
    grouped_arrows: dict[tuple[str, tuple[bool, bool, bool, bool, bool]], list[dict[str, Any]]] = {}
    for arrow in artifact.get("arrows", ()): 
        roles = dict(arrow.get("roles", {}) or {})
        signature = (
            bool(roles.get("ensured", False)),
            bool(roles.get("pareto", False)),
            bool(roles.get("counter", False)),
            bool(roles.get("semi", False)),
            bool(roles.get("super", False)),
        )
        grouped_arrows.setdefault((str(arrow.get("feature_key", "unknown")), signature), []).append(arrow)

    trace_indexes: dict[str, list[int]] = {}
    if feature_checklist:
        for (feature_key, _signature), arrows in grouped_arrows.items():
            x_values: list[float | None] = []
            y_values: list[float | None] = []
            for arrow in arrows:
                x_values.extend([arrow["x0"], arrow["x1"], None])
                y_values.extend([arrow["y0"], arrow["y1"], None])
            roles = dict(arrows[0].get("roles", {}) or {})
            _add_trace(
                fig,
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    line={"color": _ARROW_COLOR, "width": 1},
                    hoverinfo="skip",
                    meta={"trace_kind": "arrows", "feature_key": feature_key, "roles": roles},
                    legendgroup=feature_key,
                    name=f"{feature_key} arrows",
                    showlegend=False,
                ),
                side_panel=side_panel,
            )
            trace_indexes.setdefault(feature_key, []).append(_trace_count(fig) - 1)
        return trace_indexes

    for arrow in artifact.get("arrows", ()): 
        fig.add_annotation(
            x=arrow.get("x1"),
            y=arrow.get("y1"),
            ax=arrow.get("x0"),
            ay=arrow.get("y0"),
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=_ARROW_COLOR,
            opacity=0.9,
        )
    return {}


def build_side_panel_rows(artifact: PlotArtifact, options: dict[str, Any]) -> dict[str, Any]:
    if not bool(options.get("side_panel", False)):
        return {}

    return {"title": _EMPTY_PANEL_TITLE, "body_html": f"<p>{escape(_EMPTY_PANEL_BODY)}</p>"}


def _detail_markup(label: str, value: Any) -> str:
    value_markup = escape(_display_value(value)).replace("\n", "<br>")
    return (
        '<section class="ce-ensured-detail-row ce-ensured-detail-section">'
        f'<div class="ce-ensured-detail-label">{escape(label)}</div>'
        f'<div class="ce-ensured-detail-value">{value_markup}</div>'
        "</section>"
    )


def _active_role_labels(point: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    role_map = (
        ("is_ensured", "Ensured"),
        ("is_pareto", "Pareto"),
        ("is_counterfactual", "Counter"),
        ("is_counterpotential", "Super"),
        ("is_semifactual", "Semi"),
    )
    for flag_name, label in role_map:
        if bool(point.get(flag_name, False)):
            labels.append(label)
    if labels:
        return labels
    fallback_role = point.get("explanation_role")
    if fallback_role and fallback_role != "unknown":
        return [str(fallback_role).replace("_", " ").title()]
    return ["Unknown"]


def _build_side_panel_detail_payload(point: dict[str, Any]) -> dict[str, str]:
    feature_name = point.get("feature_name") or f"Feature {point.get('feature_index')}"
    title = feature_name
    roles = ", ".join(_active_role_labels(point))
    body_html = "".join(
        [
            _detail_markup("Rule", point.get("rule") or _RULE_FALLBACK),
            _detail_markup("Feature index", point.get("feature_index")),
            _detail_markup("Prediction", f"{point.get('prediction'):.6g}"),
            _detail_markup("Uncertainty", f"{point.get('uncertainty'):.6g}"),
            _detail_markup("Interval", f"[{point.get('low'):.6g}, {point.get('high'):.6g}]"),
            _detail_markup("Delta prediction", f"{point.get('delta_prediction'):+.6g}"),
            _detail_markup("Delta uncertainty", f"{point.get('delta_uncertainty'):+.6g}"),
            _detail_markup("Roles", roles),
        ]
    )
    return {"title": title, "body_html": body_html}


def build_side_panel_registry(artifact: PlotArtifact, options: dict[str, Any]) -> dict[str, dict[str, str]]:
    if not bool(options.get("side_panel", False)):
        return {}
    registry: dict[str, dict[str, str]] = {}
    for point in artifact.get("rule_points", ()): 
        point_id = point.get("id")
        if point_id is None:
            continue
        registry[str(point_id)] = _build_side_panel_detail_payload(dict(point))
    return registry


def add_side_panel(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> int | None:
    del fig, artifact, options
    return None


def add_feature_checklist_controls(fig: Any, artifact: PlotArtifact, options: dict[str, Any]) -> None:
        del fig, artifact, options


def _requires_ui_shell(options: dict[str, Any]) -> bool:
        return bool(options.get("feature_checklist", False) or options.get("side_panel", False))


def _set_trace_visible(fig: Any, index: int, visible: bool) -> None:
        trace = None
        if hasattr(fig, "data"):
                trace = fig.data[index]
        elif hasattr(fig, "traces"):
                trace = fig.traces[index]
        if trace is None:
                return
        if hasattr(trace, "kwargs"):
                trace.kwargs["visible"] = visible
        try:
                trace.visible = visible
        except Exception:
                return


def _build_feature_control_registry(
        artifact: PlotArtifact,
        trace_registry: dict[str, Any],
        options: dict[str, Any],
) -> list[dict[str, Any]]:
        if not bool(options.get("feature_checklist", False)):
                return []

        feature_groups = list(artifact.get("metadata", {}).get("feature_groups", ()))
        rule_trace_indexes = dict(trace_registry.get("rule_trace_indexes", {}) or {})
        arrow_trace_indexes = dict(trace_registry.get("arrow_trace_indexes", {}) or {})
        registry: list[dict[str, Any]] = []
        for index, group in enumerate(feature_groups):
                group_key = str(group.get("group_key"))
                trace_indexes = [
                        *list(rule_trace_indexes.get(group_key, ())),
                        *list(arrow_trace_indexes.get(group_key, ())),
                ]
                registry.append(
                        {
                                "group_key": group_key,
                                "group_label": group.get("group_label") or group_key,
                                "feature_index": group.get("feature_index"),
                                "point_count": int(group.get("point_count", len(group.get("point_ids", ())))),
                                "group_rank": int(group.get("group_rank", index)),
                                "trace_indexes": trace_indexes,
                                "default_selected": True,
                        }
                )
        return registry


def _apply_feature_control_visibility(fig: Any, trace_registry: dict[str, Any]) -> None:
        feature_registry = list(trace_registry.get("feature_control_registry", ()))
        if not feature_registry:
                trace_registry["default_visible"] = [True] * int(trace_registry.get("trace_count", 0))
                return

        trace_count = int(trace_registry.get("trace_count", 0))
        always_visible = set(trace_registry.get("always_visible", []))
        visible = [index in always_visible for index in range(trace_count)]
        for item in feature_registry:
                if not item.get("default_selected", False):
                        continue
                for trace_index in item.get("trace_indexes", ()): 
                        if 0 <= int(trace_index) < trace_count:
                                visible[int(trace_index)] = True
        for index, is_visible in enumerate(visible):
                _set_trace_visible(fig, index, bool(is_visible))
        trace_registry["default_visible"] = visible


def _figure_html(fig: Any, *, include_plotlyjs: bool | str, div_id: str) -> str:
        if hasattr(fig, "to_html"):
                return fig.to_html(
                        full_html=False,
                        include_plotlyjs=include_plotlyjs,
                        div_id=div_id,
                        config={"responsive": True},
                )

        import plotly.io as plotly_io

        return plotly_io.to_html(
                fig,
                full_html=False,
                include_plotlyjs=include_plotlyjs,
                div_id=div_id,
                config={"responsive": True},
        )


def build_render_shell_html(
        fig: Any,
        artifact: PlotArtifact,
        options: dict[str, Any],
        *,
        include_plotlyjs: bool | str,
) -> str:
        shell_id = f"ce-ensured-shell-{uuid4().hex}"
        plot_id = f"{shell_id}-plot"
        figure_html = _figure_html(fig, include_plotlyjs=include_plotlyjs, div_id=plot_id)
        show_panel = bool(options.get("side_panel", False))
        show_controls = bool(options.get("feature_checklist", False))
        empty_panel = build_side_panel_rows(artifact, options)

        panel_markup = ""
        if show_panel:
                panel_markup = (
                        '<aside class="ce-ensured-shell__panel">'
                        f'<div class="ce-ensured-panel__title" data-panel-title>{escape(empty_panel["title"])}</div>'
                        f'<div class="ce-ensured-panel__body" data-panel-body>{empty_panel["body_html"]}</div>'
                        "</aside>"
                )

        controls_markup = ""
        if show_controls:
                controls_markup = (
                        '<section class="ce-ensured-shell__controls">'
                        '<div class="ce-ensured-controls__header">Feature controls</div>'
                        '<input type="search" class="ce-ensured-controls__search" data-feature-search '
                        'placeholder="Filter by searched feature (regex)" '
                        'aria-label="Filter by searched feature using regex" />'
                        '<div class="ce-ensured-controls__actions">'
                        '<button type="button" data-feature-action="all">All</button>'
                        '<button type="button" data-feature-action="none">None</button>'
                        '<button type="button" data-feature-action="reset">Reset</button>'
                        '<button type="button" data-feature-action="ensured">Ensured</button>'
                        '<button type="button" data-feature-action="pareto">Pareto</button>'
                        '<label class="ce-ensured-controls__role">'
                        '<input type="checkbox" data-role-filter="counter" checked /> Counter'
                        '</label>'
                        '<label class="ce-ensured-controls__role">'
                        '<input type="checkbox" data-role-filter="semi" checked /> Semi'
                        '</label>'
                        '<label class="ce-ensured-controls__role">'
                        '<input type="checkbox" data-role-filter="super" checked /> Super'
                        '</label>'
                        '</div>'
                        '<div class="ce-ensured-controls__summary" data-feature-summary></div>'
                        '<div class="ce-ensured-controls__list" data-feature-list></div>'
                        '</section>'
                )

        shell_script = f"""
<script>
(function() {{
    const shell = document.getElementById({json.dumps(shell_id)});
    if (!shell) {{
        return;
    }}
    const graphDiv = shell.querySelector('.plotly-graph-div');
    const detailTitle = shell.querySelector('[data-panel-title]');
    const detailBody = shell.querySelector('[data-panel-body]');
    const searchInput = shell.querySelector('[data-feature-search]');
    const summaryNode = shell.querySelector('[data-feature-summary]');
    const listNode = shell.querySelector('[data-feature-list]');
    const actionNodes = shell.querySelectorAll('[data-feature-action]');
    const roleFilterNodes = shell.querySelectorAll('[data-role-filter]');

    function boot() {{
        if (!graphDiv || !graphDiv.data || !graphDiv.layout) {{
            window.setTimeout(boot, 40);
            return;
        }}

        const layoutMeta = graphDiv.layout.meta || {{}};
        const detailRegistry = layoutMeta.side_panel_registry || {{}};
        const featureRegistry = Array.isArray(layoutMeta.feature_control_registry) ? layoutMeta.feature_control_registry : [];
        const alwaysVisible = Array.isArray(layoutMeta.always_visible) ? layoutMeta.always_visible.slice() : [];
        const defaultSelected = {{}};
        featureRegistry.forEach((item) => {{
            defaultSelected[item.group_key] = !!item.default_selected;
        }});
        let selected = Object.assign({{}}, defaultSelected);
        const defaultRoleFilters = {{counter: true, semi: true, super: true}};
        let roleFilters = Object.assign({{}}, defaultRoleFilters);
        let rolePreset = null;

        function renderDetailPayload(payload) {{
            if (!detailTitle || !detailBody || !payload) {{
                return;
            }}
            detailTitle.textContent = payload.title || {json.dumps(_EMPTY_PANEL_TITLE)};
            detailBody.innerHTML = payload.body_html || {json.dumps(f'<p>{escape(_EMPTY_PANEL_BODY)}</p>')};
        }}

        function bindDetailPanel() {{
            if (!detailTitle || !detailBody || typeof graphDiv.on !== 'function') {{
                return;
            }}
            if (typeof graphDiv.removeAllListeners === 'function') {{
                graphDiv.removeAllListeners('plotly_click');
            }}
            graphDiv.on('plotly_click', function(eventData) {{
                const point = eventData && eventData.points && eventData.points[0];
                if (!point || point.customdata === undefined || point.customdata === null) {{
                    return;
                }}
                const payload = detailRegistry[String(point.customdata)];
                if (!payload) {{
                    return;
                }}
                renderDetailPayload(payload);
            }});
        }}

        function searchMatcher() {{
            const rawValue = ((searchInput && searchInput.value) || '').trim();
            if (!rawValue) {{
                return {{
                    active: false,
                    valid: true,
                    matches: function() {{ return true; }},
                }};
            }}
            try {{
                const regex = new RegExp(rawValue, 'i');
                return {{
                    active: true,
                    valid: true,
                    matches: function(label) {{ return regex.test(String(label || '')); }},
                }};
            }} catch (error) {{
                return {{
                    active: true,
                    valid: false,
                    matches: function() {{ return false; }},
                }};
            }}
        }}

        function updateSummary() {{
            if (!summaryNode) {{
                return;
            }}
            const total = featureRegistry.length;
            const roleSuffix = rolePreset ? `; ${{rolePreset}} points` : '';
            const matcher = searchMatcher();
            if (matcher.active) {{
                const matched = featureRegistry.filter((item) => matcher.matches(item.group_label || item.group_key)).length;
                if (!matcher.valid) {{
                    summaryNode.textContent = `Invalid regex; 0 of ${{total}} features visible`;
                }} else {{
                    summaryNode.textContent = `${{matched}} of ${{total}} features matched by search${{roleSuffix}}`;
                }}
                return;
            }}
            const active = featureRegistry.filter((item) => selected[item.group_key]).length;
            summaryNode.textContent = `${{active}} of ${{total}} features visible${{roleSuffix}}`;
        }}

        function traceMeta(traceIndex) {{
            const trace = graphDiv.data && graphDiv.data[traceIndex];
            return (trace && trace.meta) || {{}};
        }}

        function rolesAllowed(roles) {{
            const safeRoles = roles || {{}};
            if (rolePreset === 'ensured' && !safeRoles.ensured) {{
                return false;
            }}
            if (rolePreset === 'pareto' && !safeRoles.pareto) {{
                return false;
            }}
            if (rolePreset === 'ensured' || rolePreset === 'pareto') {{
                return true;
            }}
            if (safeRoles.counter && !roleFilters.counter) {{
                return false;
            }}
            if (safeRoles.semi && !roleFilters.semi) {{
                return false;
            }}
            if (safeRoles.super && !roleFilters.super) {{
                return false;
            }}
            return true;
        }}

        function applySelection() {{
            if (!featureRegistry.length) {{
                bindDetailPanel();
                return;
            }}
            const nextVisible = Array(graphDiv.data.length).fill(false);
            alwaysVisible.forEach((index) => {{
                if (index >= 0 && index < nextVisible.length) {{
                    nextVisible[index] = true;
                }}
            }});
            const matcher = searchMatcher();
            featureRegistry.forEach((item) => {{
                const label = item.group_label || item.group_key;
                const visibleBySearch = matcher.active ? matcher.matches(label) : !!selected[item.group_key];
                if (!visibleBySearch) {{
                    return;
                }}
                const ruleTraceIndexes = (item.trace_indexes || []).filter((traceIndex) => {{
                    const meta = traceMeta(traceIndex);
                    return meta.trace_kind === 'rule-points';
                }});
                const visibleRuleTraceIndexes = ruleTraceIndexes.filter((traceIndex) => {{
                    const meta = traceMeta(traceIndex);
                    return rolesAllowed(meta.roles || {{}});
                }});
                visibleRuleTraceIndexes.forEach((traceIndex) => {{
                    if (traceIndex >= 0 && traceIndex < nextVisible.length) {{
                        nextVisible[traceIndex] = true;
                    }}
                }});
                const hasVisibleRules = visibleRuleTraceIndexes.length > 0;
                (item.trace_indexes || []).forEach((traceIndex) => {{
                    const meta = traceMeta(traceIndex);
                    if (meta.trace_kind === 'rule-points') {{
                        return;
                    }}
                    if (meta.trace_kind === 'arrows' && !rolesAllowed(meta.roles || {{}})) {{
                        return;
                    }}
                    if (hasVisibleRules && traceIndex >= 0 && traceIndex < nextVisible.length) {{
                        nextVisible[traceIndex] = true;
                    }}
                }});
            }});
            const restyleResult = Plotly.restyle(graphDiv, {{visible: nextVisible}}, [...nextVisible.keys()]);
            const finishSelectionUpdate = function() {{
                updateSummary();
                bindDetailPanel();
            }};
            if (restyleResult && typeof restyleResult.then === 'function') {{
                restyleResult.then(finishSelectionUpdate);
            }} else {{
                finishSelectionUpdate();
            }}
        }}

        function renderFeatureList() {{
            if (!listNode) {{
                return;
            }}
            const matcher = searchMatcher();
            listNode.replaceChildren();
            featureRegistry.forEach((item) => {{
                const label = String(item.group_label || item.group_key || 'Feature');
                if (matcher.active && !matcher.matches(label)) {{
                    return;
                }}
                const row = document.createElement('label');
                row.className = 'ce-ensured-controls__item';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = !!selected[item.group_key];
                checkbox.addEventListener('change', () => {{
                    selected[item.group_key] = checkbox.checked;
                    applySelection();
                }});

                const text = document.createElement('span');
                text.textContent = `${{label}} (${{item.point_count}})`;

                row.appendChild(checkbox);
                row.appendChild(text);
                listNode.appendChild(row);
            }});
        }}

        if (searchInput) {{
            searchInput.addEventListener('input', () => {{
                renderFeatureList();
                applySelection();
            }});
        }}
        actionNodes.forEach((node) => {{
            node.addEventListener('click', () => {{
                const action = node.getAttribute('data-feature-action');
                if (action === 'all') {{
                    rolePreset = null;
                    roleFilters = Object.assign({{}}, defaultRoleFilters);
                    featureRegistry.forEach((item) => {{
                        selected[item.group_key] = true;
                    }});
                }} else if (action === 'none') {{
                    rolePreset = null;
                    featureRegistry.forEach((item) => {{
                        selected[item.group_key] = false;
                    }});
                }} else if (action === 'reset') {{
                    rolePreset = null;
                    roleFilters = Object.assign({{}}, defaultRoleFilters);
                    selected = Object.assign({{}}, defaultSelected);
                }} else if (action === 'ensured' || action === 'pareto') {{
                    rolePreset = action;
                    featureRegistry.forEach((item) => {{
                        selected[item.group_key] = true;
                    }});
                }}
                roleFilterNodes.forEach((roleNode) => {{
                    const filterName = roleNode.getAttribute('data-role-filter');
                    roleNode.checked = !!roleFilters[filterName];
                }});
                renderFeatureList();
                applySelection();
            }});
        }});
        roleFilterNodes.forEach((node) => {{
            node.addEventListener('change', () => {{
                const filterName = node.getAttribute('data-role-filter');
                roleFilters[filterName] = !!node.checked;
                applySelection();
            }});
        }});

        if (featureRegistry.length) {{
            renderFeatureList();
            applySelection();
        }} else {{
            updateSummary();
        }}

        bindDetailPanel();
    }}

    boot();
}})();
</script>
"""

        return f"""
<div id="{shell_id}" class="ce-ensured-shell">
    <style>
        #{shell_id}.ce-ensured-shell {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 320px;
            gap: 20px;
            align-items: start;
            font-family: Segoe UI, Helvetica, Arial, sans-serif;
            margin: 12px 0;
        }}
        #{shell_id} .ce-ensured-shell__main {{
            min-width: 0;
        }}
        #{shell_id} .ce-ensured-shell__controls {{
            border: 1px solid #d8d8d8;
            border-radius: 10px;
            background: #fafafa;
            padding: 12px;
            margin-bottom: 12px;
        }}
        #{shell_id} .ce-ensured-controls__header,
        #{shell_id} .ce-ensured-panel__title {{
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        #{shell_id} .ce-ensured-controls__search {{
            width: 100%;
            box-sizing: border-box;
            padding: 8px 10px;
            margin-bottom: 10px;
            border: 1px solid #c9c9c9;
            border-radius: 8px;
        }}
        #{shell_id} .ce-ensured-controls__actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 8px;
        }}
        #{shell_id} .ce-ensured-controls__actions button {{
            border: 1px solid #b8b8b8;
            background: white;
            border-radius: 999px;
            padding: 6px 10px;
            cursor: pointer;
        }}
        #{shell_id} .ce-ensured-controls__role {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            min-height: 30px;
            font-size: 13px;
            color: #333;
            white-space: nowrap;
        }}
        #{shell_id} .ce-ensured-controls__summary {{
            font-size: 12px;
            color: #555;
            margin-bottom: 8px;
        }}
        #{shell_id} .ce-ensured-controls__list {{
            max-height: 220px;
            overflow-y: auto;
            border-top: 1px solid #ececec;
            padding-top: 8px;
        }}
        #{shell_id} .ce-ensured-controls__item {{
            display: flex;
            gap: 8px;
            align-items: center;
            padding: 6px 0;
            font-size: 13px;
        }}
        #{shell_id} .ce-ensured-shell__panel {{
            border: 1px solid #d8d8d8;
            border-radius: 10px;
            background: #fcfcfc;
            padding: 14px;
            min-height: 320px;
            position: sticky;
            top: 12px;
        }}
        #{shell_id} .ce-ensured-panel__body {{
            font-size: 13px;
            line-height: 1.45;
            color: #222;
        }}
        #{shell_id} .ce-ensured-detail-row {{
            display: grid;
            grid-template-columns: minmax(84px, 104px) minmax(0, 1fr);
            gap: 8px;
            align-items: start;
            padding: 4px 0;
            border-bottom: 1px solid #efefef;
        }}
        #{shell_id} .ce-ensured-detail-section + .ce-ensured-detail-section {{
            margin-top: 0;
        }}
        #{shell_id} .ce-ensured-detail-label {{
            font-size: 11px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 0;
            padding-top: 2px;
        }}
        #{shell_id} .ce-ensured-detail-value {{
            white-space: normal;
            word-break: break-word;
        }}
        @media (max-width: 1100px) {{
            #{shell_id}.ce-ensured-shell {{
                grid-template-columns: minmax(0, 1fr);
            }}
            #{shell_id} .ce-ensured-shell__panel {{
                position: static;
                min-height: 0;
            }}
            #{shell_id} .ce-ensured-detail-row {{
                grid-template-columns: minmax(72px, 96px) minmax(0, 1fr);
            }}
        }}
    </style>
    <div class="ce-ensured-shell__main">
        {controls_markup}
        <div class="ce-ensured-shell__plot">{figure_html}</div>
    </div>
    {panel_markup}
</div>
{shell_script}
"""


def _layout_meta(fig: Any) -> dict[str, Any]:
    layout = getattr(fig, "layout", None)
    if isinstance(layout, dict):
        return dict(layout.get("meta", {}) or {})
    meta = getattr(layout, "meta", None)
    if isinstance(meta, dict):
        return dict(meta)
    return {}


def build_figure(artifact: PlotArtifact, options: dict[str, Any]) -> Any:
    import plotly.graph_objects as go

    axis_metadata = dict(artifact.get("axis_metadata", {}) or {})
    fig = go.Figure()

    always_visible = add_triangle_reference(fig, artifact, options)
    original_index = add_original_point(fig, artifact, options)
    if original_index is not None:
        always_visible.append(original_index)
    rule_trace_indexes = add_rule_points(fig, artifact, options)
    arrow_trace_indexes = add_arrows(fig, artifact, options)

    side_panel_registry = build_side_panel_registry(artifact, options)
    trace_registry = {
        "trace_count": _trace_count(fig),
        "always_visible": always_visible,
        "default_visible": [True] * _trace_count(fig),
        "rule_trace_indexes": rule_trace_indexes,
        "arrow_trace_indexes": arrow_trace_indexes,
        "side_panel_registry": side_panel_registry,
        "side_panel_trace_index": None,
    }
    trace_registry["feature_control_registry"] = _build_feature_control_registry(
        artifact,
        trace_registry,
        options,
    )
    _apply_feature_control_visibility(fig, trace_registry)

    fig.update_layout(
        meta=trace_registry,
        template="plotly_white",
        title="Local ensured plot",
        xaxis={
            "title": axis_metadata.get("x_label", "Probability"),
            "range": axis_metadata.get("x_range"),
        },
        yaxis={
            "title": axis_metadata.get("y_label", "Uncertainty"),
            "range": axis_metadata.get("y_range"),
        },
        margin={"l": 60, "r": 24, "t": 72, "b": 56},
        showlegend=False,
    )
    return fig


def export_html(fig: Any, path: str) -> str:
    html_path = Path(path)
    if html_path.suffix.lower() != ".html":
        html_path = html_path.with_suffix(".html")
    layout_meta = _layout_meta(fig)
    if layout_meta.get("feature_control_registry") or layout_meta.get("side_panel_registry"):
        shell_html = build_render_shell_html(
            fig,
            {"metadata": {}},
            {
                "feature_checklist": bool(layout_meta.get("feature_control_registry")),
                "side_panel": bool(layout_meta.get("side_panel_registry")),
            },
            include_plotlyjs=True,
        )
        html_path.write_text(shell_html, encoding="utf-8")
        return str(html_path)
    fig.write_html(str(html_path))
    return str(html_path)


def _display_html_shell(html_content: str) -> bool:
    try:
        from IPython.display import HTML, display
    except ImportError:
        return False
    try:
        display(HTML(html_content))
    except Exception:
        return False
    return True


class LocalEnsuredPlotRenderer(PlotRenderer):
    """Render ensured artifacts as Plotly figures."""

    plugin_meta = {
        "schema_version": 1,
        "name": RENDERER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
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
                "Plotly is required to render plotly.local.ensured. Install this package with the [plotly] extra."
            ) from exc
        shell_html = None
        if _requires_ui_shell(dict(context.options)):
            shell_html = build_render_shell_html(
                figure,
                artifact,
                dict(context.options),
                include_plotlyjs="cdn",
            )

        saved_paths: tuple[str, ...] = ()
        if context.path:
            if shell_html is not None:
                export_path = Path(context.path)
                if export_path.suffix.lower() != ".html":
                    export_path = export_path.with_suffix(".html")
                export_path.write_text(
                    build_render_shell_html(
                        figure,
                        artifact,
                        dict(context.options),
                        include_plotlyjs=True,
                    ),
                    encoding="utf-8",
                )
                saved_paths = (str(export_path),)
            else:
                saved_paths = (export_html(figure, context.path),)
        if context.show:
            if not (shell_html is not None and _display_html_shell(shell_html)):
                figure.show()
        return PlotRenderResult(
            artifact=artifact,
            figure=figure,
            saved_paths=saved_paths,
            extras={"figure": figure, "html": shell_html},
        )


__all__ = [
    "STYLE_ID",
    "ALIAS_STYLE_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "LocalEnsuredPlotBuilder",
    "LocalEnsuredPlotRenderer",
    "build_figure",
    "add_triangle_reference",
    "add_original_point",
    "add_rule_points",
    "add_arrows",
    "add_feature_checklist_controls",
    "add_side_panel",
    "build_hover_text",
    "build_side_panel_rows",
    "export_html",
]
