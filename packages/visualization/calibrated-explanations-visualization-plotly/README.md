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

The package also registers `plotly.local.alternative_feature_summary`, a local
summary for one alternative explanation. It answers which features are most
involved in the emitted local alternatives, and in what primary role plus
quality-flag combinations they appear. This is not global feature importance.

The default view is a compact horizontal stacked bar chart:

- y-axis = feature names
- x-axis = rule count, or share when `normalize="share"`
- stacked segments = role-quality combinations such as `counter`,
  `counter + ensured`, `counter + pareto`, and
  `counter + ensured + pareto`

`ensured` and `pareto` are quality flags represented inside the primary role
bars. They are not rendered as a separate default quality/status panel.
Unknown roles mean CE metadata was unavailable or unmapped; they do not mean
that a rule has no semantic role.

Role-quality keys are encoded deterministically as:

```text
primary_role[__ensured][__pareto]
```

Examples include `counter`, `counter__ensured`, `counter__pareto`,
`counter__ensured__pareto`, `semi__ensured`, and `unknown__pareto`. Primary
roles are `counter`, `super`, `semi`, and `unknown`. Longer CE labels are
normalised as `counterfactual -> counter`, `superfactual -> super`, and
`semifactual -> semi`. `counterpotential` is not silently collapsed into
`counter`; provide `role_mapping={"counterpotential": "counter"}` only when
the current CE metadata treats those labels as equivalent.

The optional conjunction panel is disabled by default. When
`include_conjunctions=True`, it counts how often each feature participates in
multi-feature rules, bucketed as `size_2`, `size_3`, or `size_4_plus`. A feature
is counted once per conjunction rule it appears in. Single-feature alternatives
are not counted as conjunctions, and conjunction counts are not merged into the
role-quality bar.

Supported alternative-feature-summary options:

- `filter_top_features`: maximum number of displayed features after sorting
- `include_conjunctions` (default `False`)
- `normalize`: `"count"` or `"share"` (default `"count"`)
- `infer_roles` (default `False`): enables conservative heuristics; inferred
  roles are marked with `role_source="heuristic"`
- `unknown_policy`: `"show"` or `"hide"` (default `"show"`)
- `sort_by`: `"total"`, `"counter"`, `"super"`, `"semi"`, `"ensured"`,
  `"pareto"`, `"conjunctions"`, or `"feature_name"`
- `orientation`: `"horizontal"`; only horizontal bars are supported in v1
- `hover_detail`: `"compact"` or `"full"`; both preserve counts and role source
  summaries in hover
- `role_mapping`: optional mapping for explicit project-specific role aliases

Role metadata is metadata-dependent. When role metadata is unavailable, the
builder records `primary_role="unknown"` and `role_source="unavailable"`.
Heuristics are never used unless `infer_roles=True`; the implemented heuristic
uses explicit role words in rule text or a probabilistic 0.5 decision-boundary
crossing for counter-like rules. The artifact preserves raw role metadata in
rule-level records where available.

The package also registers `plotly.global.instance_explorer`, a hover-only
batch/global overview for many CE instances. This is an instance explorer and
prediction/uncertainty overview, not a global CE explanation method. It plots
the central prediction quantity on the x-axis and calibrated uncertainty width
on the y-axis. Probabilistic postures, including classification and thresholded
regression, include the same probability triangle reference shape used by CE's
probabilistic triangular plots.

This style is invoked through CE's global plotting API, for example
`explainer.plot(X_test, style="plotly.global.instance_explorer")`
or `explainer.plot(X_test, y_test, style="plotly.global.instance_explorer",
...)`. When targets are supplied, classification and thresholded
probabilistic regression use one marker symbol per target class. Non-probabilistic
regression uses target values as the marker color scale.

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
None, and Reset actions. Feature visibility defaults to all shown feature
groups. The search box filters the plot by searched feature and accepts regular
expressions.

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

Alternative feature summary example:

```python
alternatives = explainer.explore_alternatives(X_query)

alternatives[0].plot(
    style="plotly.local.alternative_feature_summary",
    show=True,
)

alternatives[0].plot(
    style="plotly.local.alternative_feature_summary",
    filter_top_features=10,
    normalize="share",
    show=True,
)

alternatives[0].plot(
    style="plotly.local.alternative_feature_summary",
    include_conjunctions=True,
    show=True,
)
```

Batch instance explorer examples:

```python
classification_result = explainer.plot(
    X_query,
    style="plotly.global.instance_explorer",
    task="classification",
    position_precision=2,
    show=True,
)

classification_result_with_targets = explainer.plot(
    X_query,
    y_query,
    style="plotly.global.instance_explorer",
    task="classification",
    position_precision=2,
    show=True,
)

threshold_result = regression_explainer.plot(
    X_query,
    y_query,
    threshold=threshold,
    style="plotly.global.instance_explorer",
    task="probabilistic_regression",
    position_precision=2,
    show=True,
)

regression_result = regression_explainer.plot(
    X_query,
    y_query,
    style="plotly.global.instance_explorer",
    task="regression",
    position_precision=2,
    show=True,
)
```

Install Plotly support with:

```bash
pip install calibrated-explanations-visualization-plotly[plotly]
```

Install live dashboard support with:

```bash
pip install calibrated-explanations-visualization-plotly[live]
```

See `examples/local_ensured_plotly.ipynb` for a
`WrapCalibratedExplainer` classification and regression ensured walkthrough and
`examples/local_uncertainty_quadrant.ipynb` for the local uncertainty quadrant
example. See `examples/local_alternative_feature_summary.ipynb` for the local
alternative feature summary example and `examples/global_instance_explorer.ipynb`
for a three-section batch instance explorer walkthrough.

Dashboard examples live in the package-local `examples/` directory:

- `examples/dashboard_instance_workspace_standalone.ipynb` demonstrates
  `plotly.dashboard.instance_workspace` standalone HTML mode with precomputed
  local cards.
- `examples/dashboard_instance_workspace_live.ipynb` demonstrates
  `ce_visualization_plotly.dashboard.launch_instance_workspace(...)` live Python
  dashboard mode.
