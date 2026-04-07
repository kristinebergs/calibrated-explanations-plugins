"""SHAP visualization plugin package for calibrated explanations."""

from .plugin import (
    BOOTSTRAP_ID,
    BUILDER_ID,
    RENDERER_ID,
    STYLE_ID,
    FactualShapPlotBuilder,
    FactualShapPlotRenderer,
    FactualShapVisualizationBootstrap,
    register_factual_shap_visualization_components,
)

__all__ = [
    "BOOTSTRAP_ID",
    "BUILDER_ID",
    "RENDERER_ID",
    "STYLE_ID",
    "FactualShapPlotBuilder",
    "FactualShapPlotRenderer",
    "FactualShapVisualizationBootstrap",
    "register_factual_shap_visualization_components",
]
