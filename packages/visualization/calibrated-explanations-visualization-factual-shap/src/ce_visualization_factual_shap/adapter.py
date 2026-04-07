"""Adapter utilities for SHAP visualization plugins."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def _import_shap() -> Any:
    import shap

    return shap


def _import_pyplot() -> Any:
    import matplotlib.pyplot as plt

    return plt


def _new_figure(plt: Any) -> Any:
    """Create and activate a fresh matplotlib figure for each SHAP render."""
    return plt.figure()


def _resolve_collection(explanation_or_collection: Any) -> Any:
    if hasattr(explanation_or_collection, "batch_metadata") and hasattr(
        explanation_or_collection, "explanations"
    ):
        return explanation_or_collection

    collection = getattr(explanation_or_collection, "calibrated_explanations", None)
    if collection is not None and hasattr(collection, "batch_metadata"):
        return collection

    raise RuntimeError("SHAP visualization requires an explanation collection with batch_metadata.")


def get_shap_metadata(explanation_or_collection: Any) -> Mapping[str, Any]:
    collection = _resolve_collection(explanation_or_collection)
    metadata = getattr(collection, "batch_metadata", {})
    shap_meta = metadata.get("shap")
    if not isinstance(shap_meta, Mapping):
        raise RuntimeError("SHAP visualization requires SHAP metadata in batch_metadata['shap'].")
    return shap_meta


def _reconstruct_shap_explanation(shap_meta: Mapping[str, Any], *, bound: str) -> Any:
    shap = _import_shap()

    values_map = shap_meta.get("values")
    base_values_map = shap_meta.get("base_values")
    feature_names = shap_meta.get("feature_names")
    data = shap_meta.get("data")

    if not isinstance(values_map, Mapping) or bound not in values_map:
        raise RuntimeError(f"SHAP values metadata missing bound '{bound}'.")
    if not isinstance(base_values_map, Mapping) or bound not in base_values_map:
        raise RuntimeError(f"SHAP base_values metadata missing bound '{bound}'.")
    if feature_names is None or data is None:
        raise RuntimeError("SHAP visualization requires feature_names and data metadata.")

    return shap.Explanation(
        values=np.asarray(values_map[bound], dtype=float),
        base_values=np.asarray(base_values_map[bound], dtype=float),
        data=np.asarray(data, dtype=float),
        feature_names=list(feature_names),
    )


def to_shap_explanation(
    explanation_or_collection: Any,
    *,
    bound: str = "center",
    instance_index: int | None = None,
    prefer_runtime: bool = True,
) -> Any:
    shap_meta = get_shap_metadata(explanation_or_collection)
    explanation = None

    if prefer_runtime:
        runtime = shap_meta.get("_runtime", {})
        if isinstance(runtime, Mapping):
            explanations = runtime.get("explanations", {})
            if isinstance(explanations, Mapping):
                explanation = explanations.get(bound)

    if explanation is None:
        explanation = _reconstruct_shap_explanation(shap_meta, bound=bound)

    if instance_index is not None:
        return explanation[instance_index]
    return explanation


def plot_shap(
    explanation_or_collection: Any,
    *,
    kind: str,
    bound: str = "center",
    instance_index: int | None = None,
    prefer_runtime: bool = True,
    show: bool = True,
    **kwargs: Any,
) -> Any:
    shap = _import_shap()
    plt = _import_pyplot()

    if kind in {"waterfall", "force"} and instance_index is None:
        raise RuntimeError(f"SHAP plot kind '{kind}' requires instance_index.")

    if kind == "beeswarm":
        explanation = to_shap_explanation(
            explanation_or_collection,
            bound=bound,
            instance_index=None,
            prefer_runtime=prefer_runtime,
        )
        values = np.asarray(explanation.values, dtype=float)
        if values.ndim < 2 or values.shape[0] < 2:
            raise RuntimeError("SHAP beeswarm requires at least two instances.")
        figure = _new_figure(plt)
        shap.plots.beeswarm(explanation, show=show, **kwargs)
        return figure

    if kind == "bar":
        explanation = to_shap_explanation(
            explanation_or_collection,
            bound=bound,
            instance_index=instance_index,
            prefer_runtime=prefer_runtime,
        )
        figure = _new_figure(plt)
        shap.plots.bar(explanation, show=show, **kwargs)
        return figure

    if kind == "waterfall":
        explanation = to_shap_explanation(
            explanation_or_collection,
            bound=bound,
            instance_index=instance_index,
            prefer_runtime=prefer_runtime,
        )
        figure = _new_figure(plt)
        shap.plots.waterfall(explanation, show=show, **kwargs)
        return figure

    if kind == "force":
        explanation = to_shap_explanation(
            explanation_or_collection,
            bound=bound,
            instance_index=instance_index,
            prefer_runtime=prefer_runtime,
        )
        values = np.asarray(explanation.values, dtype=float).reshape(-1)
        features = np.asarray(explanation.data, dtype=float).reshape(-1)
        base_values = np.asarray(explanation.base_values, dtype=float).reshape(-1)
        feature_names = list(getattr(explanation, "feature_names", []) or [])
        figure = _new_figure(plt)
        shap.plots.force(
            float(base_values[0]),
            shap_values=values,
            features=features,
            feature_names=feature_names,
            matplotlib=True,
            show=show,
            **kwargs,
        )
        return figure

    raise RuntimeError(f"Unsupported SHAP plot kind '{kind}'.")
