# calibrated-explanations-visualization-plotly

Plotly visualization layouts for `calibrated-explanations`.

The package registers `plotly.local.uncertainty_quadrant`, a local factual
explanation view that plots absolute local impact against calibrated
uncertainty width. Signed contribution direction is encoded separately through
marker semantics and hover text.

The package also registers `plotly.local.ensured`, a Plotly version of CE's
existing ensured local alternative plot. It preserves the current semantics:

- x-axis = probability for probabilistic mode, prediction value for regression
- y-axis = uncertainty
- red marker = original prediction
- blue markers = alternative or rule points
- arrows = predictive movement from the original point to shown alternatives

The Plotly ensured plugin adds hover inspection, HTML export, `filter_top`, an
optional searchable feature-control panel, and an optional right-side rule
detail panel without changing CE's default `.plot()` behavior.

Compact hover is the default for `plotly.local.ensured`; blue rule points show
only rule, prediction, uncertainty, and interval unless
`hover_detail="full"` is requested.

`plotly.local.ensured_triangular` is retained as a deprecated alias for the old
name. New code should use `plotly.local.ensured`.

Supported ensured-specific options:

- `filter_top` or `max_points`
- `sort_by`
- `show_arrows`
- `show_original`
- `show_triangle_reference`
- `hover_detail`
- `include_missing_rule_points`
- `feature_checklist`
- `side_panel`

When `feature_checklist=True`, the renderer wraps the Plotly figure in a small
HTML control shell with a search box, scrollable feature toggles, and All,
None, Top-k, and Reset actions. Feature visibility defaults to the top 8 shown
feature groups so larger ensured plots remain usable.

When `side_panel=True`, a right-side text detail panel starts empty and updates
when a rule point is clicked. The panel shows the selected rule, feature,
values, prediction, uncertainty, interval, deltas, and explanation role
metadata as readable text rather than a table trace.

Role fields such as `counterfactual`, `counterpotential`, `semifactual`,
`ensured`, and `pareto` are metadata-dependent. When a role cannot be resolved
without overclaiming, the side panel and artifact use `explanation_role="unknown"`
with `role_source="unavailable"`. Heuristic role assignments, when used, are
marked with `role_source="heuristic"`.

Arrows and alternative rules visualize predictive movement only. They do not
imply causal actionability.

Core CE plotting defaults remain unchanged.

Current CE alternative custom styles are invoked from the collection-level API:

```python
alternatives = explainer.explore_alternatives(X_query)

alternatives.plot(
	style="plotly.local.ensured",
	filter_top=20,
	show=True,
)

alternatives.plot(
	style="plotly.local.ensured",
	filter_top=20,
	show=True,
	feature_checklist=True,
	side_panel=True,
)

alternatives.plot(
	style="plotly.local.ensured",
	filter_top=20,
	show=False,
	filename="ensured.html",
	feature_checklist=True,
	side_panel=True,
)
```

Install Plotly support with:

```bash
pip install calibrated-explanations-visualization-plotly[plotly]
```

See `examples/local_ensured_plotly.ipynb` for a
`WrapCalibratedExplainer` classification and regression ensured walkthrough and
`examples/local_uncertainty_quadrant.ipynb` for the local uncertainty quadrant
example.
