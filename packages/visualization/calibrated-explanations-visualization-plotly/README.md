# calibrated-explanations-visualization-plotly

Plotly visualization layouts for `calibrated-explanations`.

The package registers `plotly.local.uncertainty_quadrant`, a local factual
explanation view that plots absolute local impact against calibrated
uncertainty width. Signed contribution direction is encoded separately through
marker semantics and hover text.

Install Plotly support with:

```bash
pip install calibrated-explanations-visualization-plotly[plotly]
```

See `notebooks/local_uncertainty_quadrant.ipynb` for a `WrapCalibratedExplainer`
classification walkthrough.
