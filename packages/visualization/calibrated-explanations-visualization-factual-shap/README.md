# calibrated-explanations-visualization-factual-shap

Family: `visualization`

Status: `experimental`

> **Experimental**: this plugin has not completed a maturity review and is
> not published to PyPI. Install from source (see below).

Purpose: Separate SHAP visualization plugin package for calibrated-explanations.

Install:

```bash
git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
pip install ./calibrated-explanations-plugins/packages/visualization/calibrated-explanations-visualization-factual-shap
```

Compatibility: `calibrated-explanations>=0.11`

Style identifier:

- `official.visualization.factual.shap`

This package keeps SHAP plotting logic out of the SHAP explanation plugin. It
registers a CE visualization style and reconstructs SHAP-native inputs from the
SHAP explanation plugin metadata/runtime payload.
