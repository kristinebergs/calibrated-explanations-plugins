# calibrated-explanations-visualization-plotly

Family: `visualization`

Status: `experimental`

> The code and test evidence below target promotion to `mature`, and
> `calibrated-explanations>=1.0.0rc2` (the CE release this package's dispatch
> model requires) is now published on PyPI and installs cleanly. The
> lifecycle status remains `experimental` because this package's own PyPI
> distribution is still unclaimed with no trusted publisher configured, and
> GitHub-hosted CI has not yet run on this branch. See `MATURITY.md` for the
> full, dated audit trail.

Interactive Plotly visualization layouts for
[`calibrated-explanations`](https://github.com/kristinebergs/calibrated_explanations) (CE).

## Purpose

CE's built-in plots are static matplotlib figures. This plugin adds
interactive Plotly equivalents and extensions: hover inspection of every
rule/contribution, standalone HTML export, searchable feature controls,
batch/global instance overviews, and an optional dashboard workspace. It is
intended for practitioners who explore CE explanations in notebooks or share
self-contained interactive HTML reports.

The plugin preserves CE semantics: calibrated values, intervals, signs, and
explanation roles are taken from the CE explanation payload and are never
rescaled or re-derived. Where the CE default renderer and Plotly differ, the
difference is visual (hover cards, HTML output), not semantic.

## Installation

**Not yet on PyPI.** The distribution name
`calibrated-explanations-visualization-plotly` is intended for this package
but is unclaimed and no release has been published (verified 2026-07-20).
Once the first release exists, installation will be `pip install` of that
distribution name (with the `[live]` extra for the Dash dashboard). Until
then, install from a checkout of this repository:

```bash
pip install packages/visualization/calibrated-explanations-visualization-plotly
```

`calibrated-explanations>=1.0.0rc2,<2` (this package's dependency floor) is
now published on PyPI, so the command above resolves and installs cleanly in
a normal environment — verified in a fresh venv (`pip check` clean, full test
suite passing from the installed wheel; see `MATURITY.md`).

Plotly and NumPy are mandatory dependencies and are installed automatically;
Dash is needed only for the optional live dashboard (`[live]` extra).

Importing the package has **no side effects**: it does not register plot
styles and does not touch CE. CE's entry-point discovery
(`plugins.registry.load_entrypoint_plugins()`, e.g. via the CE plugins CLI)
finds and validates the bootstrap, but on CE 1.0.x discovery does not invoke
it. To use the styles, call the explicit registration function once:

```python
import ce_visualization_plotly as cevp

cevp.register_plotly_visualization_components()
```

Registration only adds builders/renderers/styles to CE's public registry. CE
`>=1.0.0rc2` dispatches explicit third-party styles (e.g.
`style="plotly.local.factual_bars"`) natively, with the complete option set
forwarded verbatim through `context.options` — this package never wraps,
monkey-patches, or otherwise touches `FactualExplanation.plot`,
`AlternativeExplanation.plot`, `CalibratedExplainer.plot`,
`WrapCalibratedExplainer.plot`, or `plotting.plot_global`.

## Quick start

```python
from sklearn.ensemble import RandomForestClassifier
from calibrated_explanations import WrapCalibratedExplainer

explainer = WrapCalibratedExplainer(RandomForestClassifier())
explainer.fit(X_train, y_train)
explainer.calibrate(X_cal, y_cal)

import ce_visualization_plotly as cevp

cevp.register_plotly_visualization_components()  # explicit, idempotent

factual = explainer.explain_factual(X_test)
factual[0].plot(style="plotly.local.factual_bars", show=True)

alternatives = explainer.explore_alternatives(X_test)
alternatives[0].plot(style="plotly.local.alternative_bars", show=True)

explainer.plot(X_test, style="plotly.global.instance_explorer", show=True)
```

## Available styles

| Canonical style id | Input | Meaning |
|---|---|---|
| `plotly.local.factual_bars` | one factual explanation | Signed local feature/rule contributions around zero, with a calibrated prediction header. |
| `plotly.local.factual_simple` | one factual explanation | Compact hub-style weight bars in payload order (conjunctions included): sign-coloured bars, optional interval error bars, no prediction header or ranking. |
| `plotly.local.alternative_bars` | one alternative explanation | Independent alternative scenarios as prediction deltas (not additive components). |
| `plotly.local.ensured` | alternative explanation collection | CE's ensured plot: prediction vs. uncertainty with alternative rule points and movement arrows. |
| `plotly.local.alternative_feature_summary` | one alternative explanation | Which features appear in emitted alternatives, per role and quality flags (not global importance). |
| `plotly.local.uncertainty_quadrant` | one factual explanation | Absolute local impact vs. calibrated uncertainty width, bucketed into quadrants. |
| `plotly.global.instance_explorer` | batch of instances | Hover-only prediction/uncertainty overview of many instances (not a global explanation method). |
| `plotly.dashboard.instance_workspace` | batch of instances | Standalone-HTML (or live Dash) workspace combining the instance explorer with per-instance local cards. |

`plotly.local.ensured_triangular` is retained as a **deprecated alias** for
`plotly.local.ensured`; it resolves to the same builder and renderer with no
semantic change. New code should use the canonical id.

### Support matrix

| Style | Binary clf | Multiclass clf | Thresholded/probabilistic regression | Conformal/percentile regression | Factual | Alternative | Batch input |
|---|---|---|---|---|---|---|---|
| `factual_bars` | ✅ | ⚠️ one-vs-rest header only | ✅ | ✅ | ✅ | ❌ error | per instance |
| `factual_simple` | ✅ | ⚠️ | ✅ | ✅ | ✅ | ❌ error | per instance |
| `alternative_bars` | ✅ | ⚠️ one-vs-rest | ✅ | ✅ | ❌ error | ✅ | per instance |
| `ensured` | ✅ | ⚠️ one-vs-rest | ✅ | ✅ | ❌ | ✅ | collection-level |
| `alternative_feature_summary` | ✅ | ⚠️ | ✅ | ✅ | ❌ | ✅ | per instance |
| `uncertainty_quadrant` | ✅ | ⚠️ one-vs-rest weights | ✅ | ✅ | ✅ | ❌ error | per instance |
| `instance_explorer` | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ✅ |
| `instance_workspace` | ✅ | ⚠️ | ✅ | ✅ | via cards | via cards | ✅ |

- ✅ supported and tested. ⚠️ supported with limitations: multiclass renders
  as the predicted class versus its complement (one-vs-rest); there is no
  per-class panel. The executable definition of this limitation lives in
  `tests/test_multiclass.py` (real 3-class CE workflow: every ⚠️ style must
  build and render the one-vs-rest view; factual headers caption the
  predicted class as `P(y=<label>)`/`P(y!=<label>)`).
- ❌ unsupported inputs raise a clear `ValueError` early (no silent fallback
  to another style).
- Uncertainty display for one-sided explanations raises `Warning`, matching
  CE core behaviour.
- `uncertainty_quadrant` has a fixed contract independent of task: x is the
  absolute calibrated feature weight (`|weight|`), y is the calibrated weight
  interval width (`weight_high − weight_low`). Rules without a weight and a
  two-sided weight interval are omitted with a visible `UserWarning`; if no
  rule qualifies (e.g. one-sided explanations) the builder raises
  `ValueError`. Quadrant labels bucket rules against thresholds
  (median/quantile_75/explicit) whose values and provenance are recorded in
  the artifact — they are presentation thresholds, not statistical claims.

## Configuration

Common options accepted by the local bar styles (`filter_top`, `sort_by`,
`show_uncertainty`, `hover_uncertainty`, `show_prediction_header`,
`hover_detail`) and style-specific options are validated on entry; invalid
values raise `ValueError` naming the allowed values. Highlights:

- `plotly.local.factual_bars` — `filter_top`, `sort_by`
  (`abs|value|interval_width|label|original`; default: CE core ranking via
  `rnk_metric`/`rnk_weight`), `show_uncertainty` (default `False`),
  `show_prediction_header` (default `True`), `hover_detail`
  (`compact|full`), `show_y_labels`, `show_rule_labels`. Only
  `orientation="horizontal"` is supported.
- `plotly.local.factual_simple` — `show_uncertainty` (default `False`; also
  accepts CE's `uncertainty=True` alias). Rules (including conjunctions)
  render in payload order with axis labels truncated at 32 characters; the
  full rule text is kept in the artifact and shown in hover. There is no
  prediction header, ranking, or filtering — the style intentionally mirrors
  the explainable-ai-hub factual figure.
- `plotly.local.alternative_bars` — `filter_top`, `sort_by`
  (`original|prediction_delta|interval_width|role|feature`),
  `show_uncertainty` (accepted but **ignored with a visible
  `UserWarning`** — CE core has no such toggle for alternative plots and
  calibrated intervals are always drawn), `hover_uncertainty`,
  `show_prediction_header`, `hover_detail`,
  `include_conjunctive_components` (default `True`), `unknown_policy`
  (`show|hide`).
- `plotly.local.ensured` — `filter_top`/`max_points`, `sort_by`,
  `show_arrows`, `show_original`, `show_triangle_reference`, `hover_detail`,
  `include_missing_rule_points`, `feature_checklist`, `side_panel`,
  `infer_roles` (default `False`; opt-in role heuristics, marked
  `role_source="heuristic"`), `pareto_cost`.
- `plotly.local.uncertainty_quadrant` — `threshold_strategy`
  (`median|quantile_75|explicit`, default `median`), `impact_threshold`,
  `uncertainty_threshold`, `sort_by` (default `absolute_impact`),
  `filter_top`.
- `plotly.local.alternative_feature_summary` — `filter_top_features`,
  `include_conjunctions` (default `False`), `normalize` (`count|share`),
  `infer_roles` (default `False`), `unknown_policy`, `sort_by`,
  `hover_detail`, `role_mapping`. Only horizontal orientation is supported.
- `plotly.global.instance_explorer` — `aggregate_positions` (default
  `True`), `position_precision` (default `3`), `aggregation_strategy`
  (`round|bin`), `marker_size_min`/`marker_size_max`, `task`
  (`classification|probabilistic_regression|conformal_regression|auto`),
  `class_id`, `threshold`, `low_high_percentiles`,
  `include_instance_records`, `show_triangle_reference`.
- `plotly.dashboard.instance_workspace` — `dashboard_mode`
  (`standalone_html`), `precompute` (`selected`), card selection via
  `available_cards`, plus `global_options`, `factual_options`,
  `alternative_options` forwarded to the underlying builders. Live mode is
  started with `ce_visualization_plotly.dashboard.launch_instance_workspace(...)`
  and requires the `[live]` extra.

All styles accept `show` (default `True`) and `filename`/`path` for HTML
export. Saving with `filename=` coerces the suffix to `.html` and disables
auto-show unless `show` is passed explicitly.

## Interpretation

- **Factual bars** are signed local contributions around a zero line;
  positive and negative contributions are coloured distinctly
  (classification: red/blue; regression: blue/red, matching CE defaults).
  The prediction header (probability bars or regression interval) uses an
  **independent x-axis** from the contribution bars — do not compare bar
  widths across the two panels. The complement probability bar spans
  `[1 − high, 1 − low]`.
- **Alternative bars** are **independent candidate scenarios**: each bar is
  "if this condition held, the prediction would move to X". They must not be
  summed or stacked. Conjunctive rules are expanded into indented component
  sub-bars that all share the same prediction delta because CE provides no
  per-feature decomposition for conjunctions.
- **Ensured plot**: x = probability (probabilistic) or prediction value
  (regression); y = uncertainty; red marker = original prediction; blue
  markers = alternative rule points; arrows show predictive movement.
- **Uncertainty intervals** are calibrated CE intervals; interval width is
  `high − low` and is never inverted or rescaled. Regression predictions and
  intervals are shown on the data scale and never presented as
  probabilities.
- **Explanation roles** (`counter`, `super`, `semi`) come from CE metadata.
  When metadata is unavailable the plots record `role="unknown"` with
  `role_source="unavailable"`; heuristic inference is opt-in
  (`infer_roles=True`) and always marked `role_source="heuristic"`.
- **Arrows and prediction movements are predictive statements only.** They
  never indicate causal actionability.

## Compatibility

| Dependency | Declared range | Tested versions |
|---|---|---|
| Python | `>=3.11` | 3.11.9, 3.14.4 |
| calibrated-explanations | `>=1.0.0rc2,<2` | `1.0.0rc2` (installed from real PyPI, `pip check` clean) |
| numpy | `>=1.24` (CE's own floor; direct runtime import) | 2.4.6, 2.5.1 |
| plotly | `>=5.18` | 5.18.0, 6.7.0, 6.9.0 |
| dash (optional, `[live]`) | `>=3.1` | 3.1.0, 4.4.0 (base install verified without dash) |

The dash floor is `>=3.1` because dash 2.x/3.0 pin Flask/Werkzeug versions
with known published vulnerabilities; dash 3.1 is the first release whose
dependency range admits the patched Flask 3.1.3+/Werkzeug 3.1.4+.

**CE `>=1.0.0rc2` is required, and is not optional or backward-compatible to
`rc1`.** CE `1.0.0rc1`'s public plotting API drops or rewrites several options
(`filter_top`, `uncertainty`, `rnk_metric`, `rnk_weight`, `style` itself on the
alternative path) before this package's plugin is ever invoked, and provides
no `context.runtime` for the dashboard. There is no compatibility shim for
`rc1` in this package (an earlier, since-removed version had one); installing
against `rc1` will silently drop options rather than error, so the dependency
floor is enforced rather than merely recommended.

`calibrated-explanations==1.0.0rc2` is now published on PyPI (verified
2026-07-20); this package's own dependency floor resolves and installs
cleanly from a normal `pip install`. See `MATURITY.md` for the full
reproducible evidence, including the earlier-that-day audit trail from before
the release existed.

## Assumptions and limitations

- Role metadata is metadata-dependent; without it, roles are reported as
  unknown rather than guessed (unless `infer_roles=True`, which marks its
  output as heuristic).
- Interactive output requires a browser or a notebook front-end able to
  render Plotly HTML. Very large batches degrade interactive performance;
  the instance explorer aggregates positions by default to compensate.
- `plotly.global.instance_explorer` is hover-only in this release: click
  panels and embedded local drill-down are not implemented.
- Image (PNG/SVG) export is not part of the supported scope; output is
  figure objects and standalone HTML. Use Plotly's own export tooling
  (e.g. kaleido) at your own discretion.
- Only horizontal bar orientations are supported for the bar styles.
- Registration (`register_plotly_visualization_components()`) only adds
  builders, renderers, and styles to CE's public registry. It never
  replaces, wraps, or otherwise touches any CE plotting callable —
  `FactualExplanation.plot`, `AlternativeExplanation.plot`,
  `CalibratedExplainer.plot`, `WrapCalibratedExplainer.plot`, and
  `plotting.plot_global` all keep their original identity before and after
  registration, and after rendering every style (see
  `tests/test_no_bridge_proof.py`). CE `>=1.0.0rc2` dispatches explicit
  third-party styles through its own public registry-resolution machinery
  with the complete option set, so no adapter or compatibility layer is
  needed on this package's side.
- CE's *collection*-level `.plot(...)` (e.g. `explanations.plot(...)`) warns
  visibly (`UserWarning`) on an unrecognised keyword argument. A single
  indexed explanation's `.plot(...)` (e.g. `explanations[0].plot(...)`)
  currently does **not** — an unrecognised kwarg is silently dropped. This is
  a CE-core behaviour, not something this plugin can change; see
  `MATURITY.md` "Known limitations" for the executable proof.

## Failure modes

- **Unsupported explanation kind** (e.g. alternative explanation passed to
  `factual_bars`): immediate `ValueError`.
- **Missing rule/contribution payload**: `ValueError` ("does not expose
  factual rule contributions" / "No … available for plotting").
- **Invalid option values**: `ValueError` naming the accepted values.
- **Plotly missing** (broken installation): `RuntimeError` with an
  actionable install message from every renderer.
- **Dash missing** when launching the live dashboard: `RuntimeError`
  instructing to install the `[live]` extra.
- **One-sided explanations with `show_uncertainty=True`**: `Warning`
  (CE-core-compatible behaviour).
- **Ranking is CE's own code**: both bar styles rank via CE's public
  `rank_features`/`calculate_metrics`; there is no plugin-side replica, and
  ranking failures propagate as errors rather than silently reordering.
- **Rules without two-sided weight intervals** in `uncertainty_quadrant`:
  omitted with a visible `UserWarning`; `ValueError` if nothing remains.
- Rule labels, feature names, and hover text are rendered as Plotly text
  (not raw HTML). Standalone HTML shells escape user-controlled labels
  server-side, and client-side scripts assign data values to the DOM via
  `textContent` only (never `innerHTML` concatenation), so hostile labels,
  class names, or targets render as text. This is a reviewed threat boundary
  for package-generated HTML — not a security certification, and it does not
  extend to third-party plugins composed into the same page.

## Support

- Issues: <https://github.com/kristinebergs/calibrated_explanations/issues>
  (public intake for the CE plugin ecosystem).
- Maintainer: Tuwe Löfström (`tuwe.lofstrom@ju.se`).
- Security reports: see `SECURITY.md` at the repository root.

## Examples

The package-local `examples/` directory contains notebooks for factual bars,
alternative bars, the alternative feature summary, the ensured plot, the
uncertainty quadrant, the global instance explorer, and both dashboard
modes. Notebooks are supplementary documentation; the automated test suite
is the authoritative behaviour reference.
