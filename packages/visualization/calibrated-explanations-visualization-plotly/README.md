# calibrated-explanations-visualization-plotly

Plotly visualization layouts for `calibrated-explanations`.

The package registers `plotly.local.uncertainty_quadrant`, a local factual
explanation view that plots absolute local impact against calibrated
uncertainty width. Signed contribution direction is encoded separately through
marker semantics and hover text.

The package also registers `plotly.local.ensured_triangular`, a Plotly version
of CE's existing ensured/triangular local alternative plot. It preserves the
current semantics:

- x-axis = probability for probabilistic mode, prediction value for regression
- y-axis = uncertainty
- red marker = original prediction
- blue markers = alternative or rule points
- arrows = predictive movement from the original point to shown alternatives

The Plotly plugin adds hover inspection, HTML export, and `filter_top` without
changing CE's default `.plot()` behavior. Version 0.1 intentionally does not
enable dropdown filters, click panels, side tables, or marker uncertainty
encodings, but the artifact is structured so those can be added later without
rewriting the builder.

Compact hover is the default for `plotly.local.ensured_triangular`; blue rule
points show only rule, prediction, uncertainty, and interval unless
`hover_detail="full"` is requested.

Current CE alternative custom styles are invoked from the collection-level API:

```python
alternatives = explainer.explore_alternatives(X_query)

alternatives.plot(
	style="plotly.local.ensured_triangular",
	filter_top=20,
	show=True,
)

alternatives.plot(
	style="plotly.local.ensured_triangular",
	filter_top=20,
	show=False,
	filename="ensured_triangular.html",
)
```

Install Plotly support with:

```bash
pip install calibrated-explanations-visualization-plotly[plotly]
```

See `examples/local_ensured_triangular_plotly.ipynb` for a
`WrapCalibratedExplainer` ensured/triangular walkthrough and
`examples/local_uncertainty_quadrant.ipynb` for the local uncertainty quadrant
example.
