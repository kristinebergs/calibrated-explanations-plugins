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

The package also registers `plotly.global.instance_explorer`, a hover-only
batch/global overview for many CE instances. This is an instance explorer and
prediction/uncertainty overview, not a global CE explanation method. It plots
the central prediction quantity on the x-axis and calibrated uncertainty width
on the y-axis. Probabilistic postures, including classification and thresholded
regression, include the same probability triangle reference shape used by CE's
probabilistic triangular plots.

One marker represents one or more instances. By default, positions are
aggregated deterministically by rounded x/y coordinates, so marker size reflects
how many instances share the plotted prediction/uncertainty position after
aggregation. Hover text is task-specific:

- classification: predicted class, probability, calibrated probability
  interval, interval width, and true-label summaries when supplied
- probabilistic or thresholded regression: target event, predicted event
  probability, calibrated probability interval, interval width, and observed
  event count when target values are supplied
- conformal or percentile regression: point prediction / median, percentile or
  confidence metadata, prediction interval, interval width, and observed
  interval coverage when target values are supplied

`plotly.global.instance_explorer` v1 intentionally implements hover-only
interaction. Click panels, narrative panels, and embedded local drill-down plots
are not implemented. The artifact keeps marker records, interaction capability
metadata, and optional instance records so local drill-down can be added in a
future version without changing the v1 rendering contract.

Supported instance-explorer options:

- `aggregate_positions` (default `True`)
- `position_precision` (default `3`)
- `aggregation_strategy` (`"round"` or `"bin"`, default `"round"`)
- `marker_size_min` (default `6`)
- `marker_size_max` (default `32`)
- `task` (`"classification"`, `"probabilistic_regression"`,
  `"conformal_regression"`, or `"auto"`)
- `class_id`
- `threshold`
- `low_high_percentiles`
- `include_instance_records`
- `show_triangle_reference` (default `True` for probabilistic postures)

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

Batch instance explorer examples:

```python
explanations = explainer.explain_factual(X_query)

explanations.plot(
    style="plotly.global.instance_explorer",
    task="classification",
    position_precision=2,
    show=True,
)

threshold_explanations = explainer.explain_factual(X_query, threshold=threshold)
threshold_explanations.plot(
    style="plotly.global.instance_explorer",
    task="probabilistic_regression",
    threshold=threshold,
    show=True,
)

interval_explanations = explainer.explain_factual(
    X_query,
    low_high_percentiles=(10, 90),
)
interval_explanations.plot(
    style="plotly.global.instance_explorer",
    task="conformal_regression",
    low_high_percentiles=(10, 90),
    show=True,
)
```

Install Plotly support with:

```bash
pip install calibrated-explanations-visualization-plotly[plotly]
```

See `examples/local_ensured_plotly.ipynb` for a
`WrapCalibratedExplainer` classification and regression ensured walkthrough and
`examples/local_uncertainty_quadrant.ipynb` for the local uncertainty quadrant
example. See `examples/visualization/plotly/global_instance_explorer.ipynb` for
a three-section batch instance explorer walkthrough.
