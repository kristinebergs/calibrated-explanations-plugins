from __future__ import annotations

import logging
import warnings
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from calibrated_explanations.plugins.plots import (
    PlotArtifact,
    PlotBuilder,
    PlotRenderContext,
    PlotRenderer,
    PlotRenderResult,
)

STYLE_ID = "plotly.local.alternative_feature_summary"
BUILDER_ID = "official.visualization.plotly.local.alternative_feature_summary.builder"
RENDERER_ID = "official.visualization.plotly.local.alternative_feature_summary.renderer"
ARTIFACT_VERSION = "0.2.0"

_LOGGER = logging.getLogger(__name__)
_PRIMARY_ROLES = ("counter", "super", "semi", "unknown")
_QUALITY_FLAGS = ("ensured", "pareto")
ROLE_QUALITY_KEYS = tuple(
    f"{role}{suffix}"
    for role in _PRIMARY_ROLES
    for suffix in ("", "__ensured", "__pareto", "__ensured__pareto")
)
_ROLE_ALIASES = {
    "counter": "counter",
    "counterfactual": "counter",
    "super": "super",
    "superfactual": "super",
    "semi": "semi",
    "semifactual": "semi",
    "unknown": "unknown",
}
_ROLE_QUALITY_COLORS = {
    "counter": "#2563eb",
    "counter__ensured": "#60a5fa",
    "counter__pareto": "#1d4ed8",
    "counter__ensured__pareto": "#93c5fd",
    "super": "#16a34a",
    "super__ensured": "#86efac",
    "super__pareto": "#15803d",
    "super__ensured__pareto": "#bbf7d0",
    "semi": "#d97706",
    "semi__ensured": "#fbbf24",
    "semi__pareto": "#b45309",
    "semi__ensured__pareto": "#fde68a",
    "unknown": "#64748b",
    "unknown__ensured": "#94a3b8",
    "unknown__pareto": "#475569",
    "unknown__ensured__pareto": "#cbd5e1",
}
_CONJUNCTION_COLORS = {
    "size_1": "#94d2bd",
    "size_2": "#0f766e",
    "size_3": "#14b8a6",
    "size_4_plus": "#99f6e4",
}


def _warn_fallback(reason: str) -> None:
    message = f"Plotly alternative feature summary fallback: {reason}"
    _LOGGER.info(message)
    warnings.warn(message, UserWarning, stacklevel=3)


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


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


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
    is_alternative = getattr(local_explanation, "is_alternative", None)
    if callable(is_alternative):
        return bool(is_alternative())
    if isinstance(is_alternative, bool):
        return is_alternative
    return "alternative" in type(local_explanation).__name__.lower()


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


def _mode_metadata(explanation: Any, local_explanation: Any) -> dict[str, Any]:
    batch_metadata = dict(getattr(explanation, "batch_metadata", {}) or {})
    get_mode = getattr(local_explanation, "get_mode", None)
    raw_mode = get_mode() if callable(get_mode) else batch_metadata.get("mode")
    is_regression = bool(getattr(local_explanation, "is_regression", lambda: False)())
    is_probabilistic = bool(getattr(local_explanation, "is_probabilistic", lambda: False)())
    task = batch_metadata.get("task")
    if task is None:
        task = "regression" if is_regression else "classification" if is_probabilistic else raw_mode
    return {
        "task": task,
        "mode": raw_mode or task,
        "is_regression": is_regression,
        "is_probabilistic": is_probabilistic,
    }


def _resolve_alternative_rules(local_explanation: Any) -> dict[str, Any]:
    get_rules = getattr(local_explanation, "get_rules", None)
    rules = get_rules() if callable(get_rules) else getattr(local_explanation, "rules", None)
    if not isinstance(rules, Mapping):
        raise ValueError("The explanation does not expose alternative-rule data.")
    return dict(rules)


def _normalise_feature_indices(feature: Any) -> list[Any]:
    if isinstance(feature, np.ndarray):
        return feature.ravel().tolist()
    if isinstance(feature, (list, tuple, set)):
        return list(feature)
    return [feature]


def _values_for_features(value: Any, feature_count: int) -> list[Any]:
    if isinstance(value, np.ndarray):
        value = value.ravel().tolist()
    if isinstance(value, (list, tuple)) and len(value) == feature_count:
        return [_serialise_value(item) for item in value]
    return [_serialise_value(value) for _ in range(feature_count)]


def _conjunction_size(feature_indices: list[Any], rule: str, is_conjunctive: bool) -> int:
    if len(feature_indices) > 1:
        return len(feature_indices)
    if not is_conjunctive:
        return 1
    normalised_rule = str(rule or "").replace("& \n", " AND ").replace("\n", " ")
    if " AND " in normalised_rule:
        return max(1, len([part for part in normalised_rule.split(" AND ") if part.strip()]))
    if " & " in normalised_rule:
        return max(1, len([part for part in normalised_rule.split(" & ") if part.strip()]))
    return 2


def _conjunction_bucket(rule_size: int) -> str:
    if rule_size <= 1:
        return "size_1"
    if rule_size == 2:
        return "size_2"
    if rule_size == 3:
        return "size_3"
    return "size_4_plus"


def _role_quality_key(primary_role: str, quality_flags: list[str]) -> str:
    suffix = "".join(f"__{flag}" for flag in _QUALITY_FLAGS if flag in quality_flags)
    return f"{primary_role}{suffix}"


def _role_quality_label(key: str) -> str:
    return key.replace("__", " + ")


def _normalise_role(raw_role: Any, role_mapping: Mapping[str, str] | None) -> str:
    if raw_role is None:
        return "unknown"
    raw = str(raw_role).strip().lower()
    if not raw:
        return "unknown"
    mapping = dict(role_mapping or {})
    if raw in mapping:
        raw = str(mapping[raw]).strip().lower()
    return _ROLE_ALIASES.get(raw, "unknown")


def _rule_array_value(rules: dict[str, Any], keys: tuple[str, ...], rule_index: int) -> Any:
    for key in keys:
        values = rules.get(key)
        if values is not None:
            value = _sequence_get(values, rule_index)
            if value is not None:
                return value
    return None


def _identity_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return tuple(_identity_value(item) for item in value.ravel().tolist())
    if isinstance(value, (list, tuple)):
        return tuple(_identity_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _identity_value(item)) for key, item in value.items()))
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _rule_identity(rules: dict[str, Any], rule_index: int) -> tuple[Any, ...]:
    return tuple(
        _identity_value(_sequence_get(rules.get(key, ()), rule_index))
        for key in ("rule", "feature", "predict", "predict_low", "predict_high")
    )


def _matching_rule_indices(
    original_rules: dict[str, Any], filtered_rules: dict[str, Any]
) -> set[int]:
    filtered_identities = {
        _rule_identity(filtered_rules, index)
        for index in range(len(filtered_rules.get("rule", ())))
    }
    return {
        index
        for index in range(len(original_rules.get("rule", ())))
        if _rule_identity(original_rules, index) in filtered_identities
    }


def _filtered_rules_from_method(
    local_explanation: Any, method_names: tuple[str, ...]
) -> dict[str, Any] | None:
    for method_name in method_names:
        method = getattr(local_explanation, method_name, None)
        if not callable(method):
            continue
        for kwargs in (
            {"include_potential": True, "copy": True},
            {"only_ensured": False, "include_potential": True, "copy": True},
            {"copy": True},
            {},
        ):
            try:
                filtered = method(**kwargs)
            except TypeError:
                continue
            try:
                return _resolve_alternative_rules(filtered)
            except ValueError:
                continue
    return None


def _resolve_ce_memberships(local_explanation: Any, rules: dict[str, Any]) -> dict[str, set[int]]:
    method_map = {
        "counter": ("counter", "counter_explanations"),
        "super": ("super", "super_explanations"),
        "semi": ("semi", "semi_explanations"),
        "ensured": ("ensured", "ensured_explanations"),
        "pareto": ("pareto", "pareto_explanations"),
    }
    memberships: dict[str, set[int]] = {}
    for role_name, method_names in method_map.items():
        filtered_rules = _filtered_rules_from_method(local_explanation, method_names)
        if filtered_rules is not None:
            memberships[role_name] = _matching_rule_indices(rules, filtered_rules)
    return memberships


def _resolve_primary_role(
    *,
    rules: dict[str, Any],
    rule_index: int,
    rule_condition: str,
    prediction: float | None,
    base_prediction: float | None,
    mode_metadata: dict[str, Any],
    options: dict[str, Any],
    ce_memberships: dict[str, set[int]],
) -> tuple[str, str, dict[str, Any]]:
    role_mapping = options.get("role_mapping")
    if role_mapping is not None and not isinstance(role_mapping, Mapping):
        raise ValueError("role_mapping must be a mapping or None.")

    explicit_role = _rule_array_value(
        rules,
        ("primary_role", "alternative_role", "explanation_role", "role", "type", "kind"),
        rule_index,
    )
    if explicit_role is not None:
        return (
            _normalise_role(explicit_role, role_mapping),
            "rule_metadata",
            {"raw_role": explicit_role},
        )

    for role in ("counter", "super", "semi"):
        if rule_index in ce_memberships.get(role, set()):
            return role, "ce_metadata", {"raw_role": role}

    role_flags = {
        "counter": ("is_counter", "counter", "is_counterfactual", "counterfactual"),
        "super": ("is_super", "super", "is_superfactual", "superfactual"),
        "semi": ("is_semi", "semi", "is_semifactual", "semifactual"),
    }
    for role, keys in role_flags.items():
        for key in keys:
            value = _rule_array_value(rules, (key,), rule_index)
            if _as_bool(value) is True:
                return role, "rule_metadata", {"raw_role": key}

    if bool(options.get("infer_roles", False)):
        # Conservative heuristic: infer counter only when a probabilistic rule
        # crosses the base 0.5 decision boundary. Text labels are used only when
        # they contain explicit role words. Every inferred role is marked below.
        lowered = rule_condition.lower()
        if "counterfactual" in lowered:
            return "counter", "heuristic", {"heuristic": "rule_text_contains_counterfactual"}
        if "semifactual" in lowered:
            return "semi", "heuristic", {"heuristic": "rule_text_contains_semifactual"}
        if "superfactual" in lowered:
            return "super", "heuristic", {"heuristic": "rule_text_contains_superfactual"}
        if (
            mode_metadata.get("is_probabilistic")
            and prediction is not None
            and base_prediction is not None
        ) and (prediction >= 0.5) != (base_prediction >= 0.5):
            return "counter", "heuristic", {"heuristic": "probability_crosses_0_5_boundary"}

    return "unknown", "unavailable", {"raw_role": explicit_role}


def _resolve_quality_flag(rules: dict[str, Any], rule_index: int, keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = _rule_array_value(rules, (key,), rule_index)
        resolved = _as_bool(value)
        if resolved is not None:
            return resolved
    return False


def _empty_feature_summary(
    *,
    feature_index: Any,
    feature_name: str,
    true_value: Any,
) -> dict[str, Any]:
    return {
        "feature_index": feature_index,
        "feature_name": feature_name,
        "true_value": true_value,
        "total_rule_count": 0,
        "role_quality_counts": dict.fromkeys(ROLE_QUALITY_KEYS, 0),
        "primary_role_counts": dict.fromkeys(_PRIMARY_ROLES, 0),
        "quality_flag_counts": dict.fromkeys(_QUALITY_FLAGS, 0),
        "conjunction_counts": {"size_1": 0, "size_2": 0, "size_3": 0, "size_4_plus": 0, "total": 0},
        "rule_ids_by_role_quality": {key: [] for key in ROLE_QUALITY_KEYS},
        "rule_ids_by_conjunction_size": {
            "size_1": [],
            "size_2": [],
            "size_3": [],
            "size_4_plus": [],
        },
        "role_source_counts": {
            "ce_metadata": 0,
            "rule_metadata": 0,
            "heuristic": 0,
            "unavailable": 0,
        },
        "metadata": {},
    }


def _sort_feature_summaries(
    summaries: list[dict[str, Any]],
    *,
    sort_by: str,
    include_conjunctions: bool,
) -> list[dict[str, Any]]:
    def sort_value(item: dict[str, Any]) -> int | str:
        if sort_by == "feature_name":
            return str(item.get("feature_name", "")).lower()
        if sort_by == "ensured":
            return int(item["quality_flag_counts"]["ensured"])
        if sort_by == "pareto":
            return int(item["quality_flag_counts"]["pareto"])
        if sort_by in {"counter", "super", "semi"}:
            return int(item["primary_role_counts"][sort_by])
        if sort_by == "conjunctions":
            return (
                int(item["conjunction_counts"]["total"])
                if include_conjunctions
                else int(item["total_rule_count"])
            )
        return int(item["total_rule_count"])

    if sort_by == "feature_name":
        return sorted(summaries, key=lambda item: (sort_value(item), item.get("feature_index")))
    return sorted(
        summaries,
        key=lambda item: (
            -int(sort_value(item)),
            str(item.get("feature_name", "")),
            str(item.get("feature_index")),
        ),
    )


def _compact_rule_ids(rule_ids: list[str], limit: int = 8) -> str:
    if len(rule_ids) <= limit:
        return ", ".join(rule_ids)
    return ", ".join(rule_ids[:limit]) + f", +{len(rule_ids) - limit} more"


def _role_hover_text(summary: dict[str, Any], key: str, count: int, normalize: str) -> str:
    total = max(1, int(summary.get("total_rule_count", 0)))
    flags = [flag for flag in _QUALITY_FLAGS if f"__{flag}" in key]
    primary_role = key.split("__", 1)[0]
    source_counts = (
        summary.get("metadata", {}).get("role_source_counts_by_role_quality", {}).get(key, {})
    )
    lines = [
        f"feature: {summary.get('feature_name')}",
        f"feature index: {summary.get('feature_index')}",
        f"current value: {summary.get('true_value')}",
        f"role-quality: {_role_quality_label(key)}",
        f"primary role: {primary_role}",
        "quality flags: " + (", ".join(flags) if flags else "none"),
        f"count: {count}",
        f"share within feature: {count / total:.3f}",
        "rule ids/ranks: " + _compact_rule_ids(summary["rule_ids_by_role_quality"].get(key, [])),
        "role sources: "
        + ", ".join(
            f"{source}={int(source_counts.get(source, 0))}"
            for source in ("ce_metadata", "rule_metadata", "heuristic", "unavailable")
        ),
    ]
    if normalize == "share":
        lines.append("bar value: share")
    return "<br>".join(lines)


def _conjunction_hover_text(summary: dict[str, Any], bucket: str, count: int) -> str:
    return "<br>".join(
        [
            f"feature: {summary.get('feature_name')}",
            f"conjunction size bucket: {bucket}",
            f"count: {count}",
            "rule ids/ranks: "
            + _compact_rule_ids(summary["rule_ids_by_conjunction_size"].get(bucket, [])),
        ]
    )


class AlternativeFeatureSummaryPlotBuilder(PlotBuilder):
    """Build a local feature summary artifact for CE alternative rules."""

    plugin_meta = {
        "schema_version": 1,
        "name": BUILDER_ID,
        "version": ARTIFACT_VERSION,
        "provider": "plotly.local",
        "data_modalities": ("tabular",),
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
            raise ValueError(f"{STYLE_ID} supports alternative local explanations only.")

        options = dict(context.options)
        normalize = str(options.get("normalize", "count"))
        if normalize not in {"count", "share"}:
            raise ValueError("normalize must be 'count' or 'share'.")
        unknown_policy = str(options.get("unknown_policy", "show"))
        if unknown_policy not in {"show", "hide"}:
            raise ValueError("unknown_policy must be 'show' or 'hide'.")
        sort_by = str(options.get("sort_by", "total"))
        if sort_by not in {
            "total",
            "counter",
            "super",
            "semi",
            "ensured",
            "pareto",
            "conjunctions",
            "feature_name",
        }:
            raise ValueError("Unsupported sort_by value for alternative feature summary.")
        orientation = str(options.get("orientation", "horizontal"))
        if orientation != "horizontal":
            raise ValueError("Only horizontal orientation is supported in v1.")
        hover_detail = str(options.get("hover_detail", "compact"))
        if hover_detail not in {"compact", "full"}:
            raise ValueError("hover_detail must be 'compact' or 'full'.")

        local_explanation = _select_local_explanation(
            context.explanation, options.get("instance_index")
        )
        if not _is_alternative_explanation(local_explanation):
            raise ValueError(f"{STYLE_ID} requires an alternative explanation.")

        rules = _resolve_alternative_rules(local_explanation)
        mode_metadata = _mode_metadata(context.explanation, local_explanation)
        collection = _collection_for(local_explanation)
        prediction_header = dict(getattr(local_explanation, "prediction", {}) or {})
        base_prediction = _as_float(prediction_header.get("predict"))
        rule_labels = list(rules.get("rule", ()))
        num_rules = len(rule_labels)
        ce_memberships = _resolve_ce_memberships(local_explanation, rules)
        feature_summaries_by_key: dict[str, dict[str, Any]] = {}
        source_counts_by_feature_key: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"ce_metadata": 0, "rule_metadata": 0, "heuristic": 0, "unavailable": 0}
            )
        )
        rule_records: list[dict[str, Any]] = []
        num_unknown_roles = 0

        for rule_index in range(num_rules):
            raw_rule = _sequence_get(rule_labels, rule_index, f"rule {rule_index}")
            rule_condition = str(raw_rule).strip() if raw_rule is not None else f"rule {rule_index}"
            raw_feature = _sequence_get(rules.get("feature", ()), rule_index)
            feature_indices = _normalise_feature_indices(raw_feature)
            feature_names = [
                _feature_name(collection, feature_index) or f"Feature {feature_index}"
                for feature_index in feature_indices
            ]
            raw_true_value = _sequence_get(
                rules.get("feature_value", ()),
                rule_index,
                _sequence_get(rules.get("value", ()), rule_index),
            )
            true_values = _values_for_features(raw_true_value, len(feature_indices))
            is_conjunctive = bool(
                _as_bool(_sequence_get(rules.get("is_conjunctive", ()), rule_index)) or False
            )
            rule_size = _conjunction_size(feature_indices, rule_condition, is_conjunctive)
            is_conjunction = rule_size > 1
            prediction = _as_float(_sequence_get(rules.get("predict", ()), rule_index))
            low = _as_float(_sequence_get(rules.get("predict_low", ()), rule_index))
            high = _as_float(_sequence_get(rules.get("predict_high", ()), rule_index))
            uncertainty = (high - low) if high is not None and low is not None else None
            primary_role, role_source, role_metadata = _resolve_primary_role(
                rules=rules,
                rule_index=rule_index,
                rule_condition=rule_condition,
                prediction=prediction,
                base_prediction=base_prediction,
                mode_metadata=mode_metadata,
                options=options,
                ce_memberships=ce_memberships,
            )
            if primary_role == "unknown":
                num_unknown_roles += 1
            is_ensured = _resolve_quality_flag(
                rules,
                rule_index,
                ("is_ensured", "ensured", "ensured_rule", "is_ensured_rule"),
            ) or rule_index in ce_memberships.get("ensured", set())
            is_pareto = _resolve_quality_flag(
                rules,
                rule_index,
                ("is_pareto", "pareto", "pareto_optimal", "is_pareto_optimal"),
            ) or rule_index in ce_memberships.get("pareto", set())
            quality_flags = [
                flag for flag, active in (("ensured", is_ensured), ("pareto", is_pareto)) if active
            ]
            role_quality_key = _role_quality_key(primary_role, quality_flags)
            role_quality_label = _role_quality_label(role_quality_key)
            rank_value = _sequence_get(rules.get("rank", ()), rule_index, rule_index + 1)
            rule_id = str(_sequence_get(rules.get("rule_id", ()), rule_index, f"rule-{rule_index}"))
            if rank_value is not None:
                rule_id = f"{rule_id} (rank {rank_value})"

            record = {
                "rule_id": rule_id,
                "rank": rank_value,
                "feature_indices": [_serialise_value(item) for item in feature_indices],
                "feature_names": feature_names,
                "true_values": true_values,
                "rule": rule_condition,
                "rule_size": rule_size,
                "is_conjunction": is_conjunction,
                "primary_role": primary_role,
                "quality_flags": quality_flags,
                "role_quality_key": role_quality_key,
                "role_quality_label": role_quality_label,
                "role_source": role_source,
                "is_counter": primary_role == "counter",
                "is_super": primary_role == "super",
                "is_semi": primary_role == "semi",
                "is_ensured": is_ensured,
                "is_pareto": is_pareto,
                "prediction": prediction,
                "low": low,
                "high": high,
                "uncertainty": uncertainty,
                "metadata": role_metadata,
            }
            rule_records.append(record)

            if unknown_policy == "hide" and primary_role == "unknown":
                continue
            conjunction_bucket = _conjunction_bucket(rule_size)
            for position, feature_index in enumerate(feature_indices):
                feature_name = feature_names[position]
                true_value = true_values[position] if position < len(true_values) else None
                summary_key = f"{feature_index!r}:{feature_name}"
                summary = feature_summaries_by_key.setdefault(
                    summary_key,
                    _empty_feature_summary(
                        feature_index=_serialise_value(feature_index),
                        feature_name=feature_name,
                        true_value=true_value,
                    ),
                )
                summary["total_rule_count"] += 1
                summary["role_quality_counts"][role_quality_key] += 1
                summary["primary_role_counts"][primary_role] += 1
                for flag in quality_flags:
                    summary["quality_flag_counts"][flag] += 1
                summary["rule_ids_by_role_quality"][role_quality_key].append(rule_id)
                summary["role_source_counts"][role_source] += 1
                source_counts_by_feature_key[summary_key][role_quality_key][role_source] += 1
                summary["conjunction_counts"][conjunction_bucket] += 1
                summary["conjunction_counts"]["total"] += 1
                summary["rule_ids_by_conjunction_size"][conjunction_bucket].append(rule_id)

        feature_summaries = list(feature_summaries_by_key.values())
        for summary_key, summary in zip(
            feature_summaries_by_key.keys(), feature_summaries, strict=False
        ):
            summary["metadata"]["role_source_counts_by_role_quality"] = dict(
                source_counts_by_feature_key[summary_key]
            )

        include_conjunctions = bool(options.get("include_conjunctions", False))
        feature_summaries = _sort_feature_summaries(
            feature_summaries,
            sort_by=sort_by,
            include_conjunctions=include_conjunctions,
        )
        filter_top_features = options.get("filter_top_features")
        if filter_top_features is not None:
            feature_summaries = feature_summaries[: int(filter_top_features)]

        included_keys = [
            key
            for key in ROLE_QUALITY_KEYS
            if any(summary["role_quality_counts"].get(key, 0) for summary in feature_summaries)
        ]
        num_conjunction_rules = sum(1 for record in rule_records if record["is_conjunction"])

        return {
            "artifact_type": STYLE_ID,
            "artifact_version": ARTIFACT_VERSION,
            "style": STYLE_ID,
            "mode": mode_metadata.get("mode"),
            "task": mode_metadata.get("task"),
            "instance_metadata": {
                "instance_index": getattr(
                    local_explanation, "index", options.get("instance_index")
                ),
                "prediction": prediction_header,
            },
            "rule_records": rule_records,
            "feature_summaries": feature_summaries,
            "role_quality_keys": included_keys,
            "panel_config": {
                "show_role_quality_summary": True,
                "show_conjunctions": include_conjunctions,
                "normalize": normalize,
                "sort_by": sort_by,
                "filter_top_features": filter_top_features,
                "hover_detail": hover_detail,
            },
            "metadata": {
                "num_rules": len(rule_records),
                "num_features": len(feature_summaries),
                "num_conjunction_rules": num_conjunction_rules,
                "num_unknown_roles": num_unknown_roles,
                "num_role_quality_combinations": len(included_keys),
                "infer_roles": bool(options.get("infer_roles", False)),
                "unknown_policy": unknown_policy,
                "role_mapping": dict(options.get("role_mapping") or {}),
                "created_by": STYLE_ID,
            },
        }


class AlternativeFeatureSummaryPlotRenderer(PlotRenderer):
    """Render local alternative feature summaries as Plotly stacked bars."""

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
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError as exc:
            raise RuntimeError(
                f"Plotly is required to render {STYLE_ID}. "
                "Install this package with the [plotly] extra."
            ) from exc

        summaries = list(artifact.get("feature_summaries", ()))
        role_quality_keys = list(artifact.get("role_quality_keys", ()))
        panel_config = dict(artifact.get("panel_config", {}) or {})
        include_conjunctions = bool(panel_config.get("show_conjunctions", False))
        normalize = str(panel_config.get("normalize", "count"))
        rows = 2 if include_conjunctions else 1
        titles = ["Primary role and quality-flag combinations"]
        if include_conjunctions:
            titles.append("Conjunction involvement")
        figure = make_subplots(rows=rows, cols=1, shared_yaxes=True, subplot_titles=titles)

        y_values = [summary["feature_name"] for summary in summaries]
        for key in role_quality_keys:
            raw_counts = [int(summary["role_quality_counts"].get(key, 0)) for summary in summaries]
            x_values = [
                (count / max(1, int(summary.get("total_rule_count", 0))))
                if normalize == "share"
                else count
                for count, summary in zip(raw_counts, summaries, strict=False)
            ]
            hover = [
                _role_hover_text(summary, key, count, normalize)
                for summary, count in zip(summaries, raw_counts, strict=False)
            ]
            figure.add_trace(
                go.Bar(
                    x=x_values,
                    y=y_values,
                    orientation="h",
                    name=_role_quality_label(key),
                    marker={"color": _ROLE_QUALITY_COLORS.get(key, "#64748b")},
                    customdata=raw_counts,
                    hovertext=hover,
                    hovertemplate="%{hovertext}<extra></extra>",
                    meta={"panel": "role_quality", "role_quality_key": key},
                ),
                row=1,
                col=1,
            )

        if include_conjunctions:
            if not any(summary["conjunction_counts"]["total"] for summary in summaries):
                figure.add_annotation(
                    text="No conjunction rules are available for this explanation.",
                    xref="x2 domain",
                    yref="y2 domain",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                )
            for bucket in ("size_1", "size_2", "size_3", "size_4_plus"):
                raw_counts = [
                    int(summary["conjunction_counts"].get(bucket, 0)) for summary in summaries
                ]
                x_values = [
                    (count / max(1, int(summary.get("total_rule_count", 0))))
                    if normalize == "share"
                    else count
                    for count, summary in zip(raw_counts, summaries, strict=False)
                ]
                hover = [
                    _conjunction_hover_text(summary, bucket, count)
                    for summary, count in zip(summaries, raw_counts, strict=False)
                ]
                figure.add_trace(
                    go.Bar(
                        x=x_values,
                        y=y_values,
                        orientation="h",
                        name=bucket,
                        marker={"color": _CONJUNCTION_COLORS[bucket]},
                        customdata=raw_counts,
                        hovertext=hover,
                        hovertemplate="%{hovertext}<extra></extra>",
                        meta={"panel": "conjunctions", "bucket": bucket},
                    ),
                    row=2,
                    col=1,
                )

        figure.update_layout(
            template="plotly_white",
            title="Local alternative feature summary",
            barmode="stack",
            legend_title_text="Role-quality combination",
            margin={"l": 5, "r": 24, "t": 60, "b": 40},
            autosize=True,
            meta={"artifact_type": STYLE_ID, "panel_config": panel_config},
        )
        x_title = "Share of rules" if normalize == "share" else "Rule count"
        if hasattr(figure, "update_xaxes"):
            figure.update_xaxes(title_text=x_title, row=1, col=1)
            if include_conjunctions:
                figure.update_xaxes(title_text=x_title, row=2, col=1)
        if hasattr(figure, "update_yaxes"):
            figure.update_yaxes(autorange="reversed", automargin=True, row=1, col=1)
            if include_conjunctions:
                figure.update_yaxes(autorange="reversed", automargin=True, row=2, col=1)

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
    "ARTIFACT_VERSION",
    "BUILDER_ID",
    "RENDERER_ID",
    "ROLE_QUALITY_KEYS",
    "STYLE_ID",
    "AlternativeFeatureSummaryPlotBuilder",
    "AlternativeFeatureSummaryPlotRenderer",
]
