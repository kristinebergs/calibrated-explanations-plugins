# Maturity evidence — calibrated-explanations-visualization-plotly 0.3.0

Reviewed 2026-07-16 for promotion `experimental` → `mature`.

## Supported scope

Eight styles (see README support matrix): `plotly.local.factual_bars`,
`plotly.local.factual_simple`, `plotly.local.alternative_bars`,
`plotly.local.ensured` (+ deprecated alias `plotly.local.ensured_triangular`),
`plotly.local.alternative_feature_summary`,
`plotly.local.uncertainty_quadrant`, `plotly.global.instance_explorer`,
`plotly.dashboard.instance_workspace`. Multiclass is limited to a
one-vs-rest view; `uncertainty_quadrant` is supported-with-limitations
across all postures. Unsupported inputs raise `ValueError` early; no silent
style substitution.

## Parity-failure classification

Historical record said 28 failures; the current suite showed **5** at
baseline (commit `3e06eca`), all in `tests/parity/test_plotly_bars_parity.py`:

| Failing cases | Classification | Root cause | Action |
|---|---|---|---|
| `test_factual_bars_all_widths_are_04` (3 cases) | Plugin defect | Bar traces omitted `width=0.4`; CE mpl adapter draws factual bars as `fill_betweenx(x±0.2)` (span 0.4). Code comment justifying 0.8 was factually wrong. | Set `width=0.4` on body and header bar traces (`factual_bars.py`). |
| `test_factual_bars_uncertainty_overlays_drawn_after_solid` (2 cases) | Plugin defect | Interval traces added before solid bars, inverting the mpl paint order (solid first, translucent overlay on top). | Reordered: solid trace first, interval overlays after. |

One skip remains: `…overlays_drawn_after_solid[factual_probabilistic_no_uncertainty]`
— parametrized guard ("No interval data in this case"), not a hidden failure.
Result: **0 unexplained parity failures** (parity suite fully green).

Additional defects found and fixed during review:

- `factual_bars.py` imported `calibrated_explanations.utils.metrics` (module
  does not exist in CE 1.0) inside `contextlib.suppress`, silently disabling
  non-default ranking. Fixed to `utils.helper.calculate_metrics`.
- Builders rejected `rnk_metric=None` / `rnk_weight=None` forwarded by CE's
  collection-level plot; `None` now means "use style default"
  (found by the generalized wheel-gate smoke render).

## Public-API audit

Used CE surfaces: `plugins.plots` (plugin contract), `plugins.registry`
(public registration/lookup), `plugins` (`ensure_builtin_plugins`,
`PlotRenderContext`), `utils.exceptions.ConfigurationError`,
`utils.helper.calculate_metrics`, `viz.builders` (PlotSpec extension
surface; legacy color helpers in `alternative_bars` have an inline fallback),
`explanations.explanation.{Factual,Alternative}Explanation` (public classes),
`plotting.plot_global` (module attribute, wrapped at registration).

Removed in this review: monkey-patches of `CalibratedExplainer.plot` and
`WrapCalibratedExplainer.plot` (redundant on CE >= 1.0, which resolves
`plot_global` at call time) — this also removed all uses of CE-private
members (`_assert_fitted`, `_cfg`, `_get_bins`, `_last_explanation_mode`).
Remaining upstream gap (documented, tested at the boundary in
`tests/test_package_contract.py` and `tests/test_instance_workspace.py`):
CE explanation-level `.plot()` consumes `filter_top`/`uncertainty`/
`rnk_metric`/`rnk_weight`/`filename`/`show` before custom-style dispatch, so
the package wraps those two public `.plot` methods and the `plot_global`
module attribute.

## Wheel and entry-point evidence

`python scripts/runtime_check_package.py --package-path <pkg>` passes
(exit 0): wheel built, installed into a fresh venv with CE from PyPI;
entry-point discovery and trust registration validated from the installed
wheel; 7 styles smoke-rendered through public CE APIs per declared intent,
dashboard style registry-validated; plugin docstring coverage 100%; venv
pytest 192 passed / 1 skipped with coverage 81.85% (gate: 80%).
`scripts/runtime_harness.py` was generalized in this review to support
multi-style visualization packages (builder/renderer entry points as named
pairs plus per-style `intent` metadata); it previously hard-required exactly
one builder/renderer.

`tests/test_package_contract.py` (added) covers: declared entry points load
and match runtime registration; bootstrap `plugin_meta.version` equals
`project.version`; registration idempotence; deprecated alias resolution;
import-time side-effect freedom (no file writes, no sockets); actionable
missing-backend errors; HTML escaping of hostile labels; Unicode/long
labels; output-suffix coercion and documented overwrite behaviour.

## Compatibility matrix tested

| Environment | Python | CE | plotly | dash | Result |
|---|---|---|---|---|---|
| Dev (source) | 3.11.9 | 1.0.0rc1 | 6.7.0 | 4.1.0 | 192 passed, 1 skipped |
| Wheel gate venv | 3.11.9 | 1.0.0rc1 (PyPI) | latest | — | gate exit 0; 192 passed, cov 81.85% |
| Newest boundary (wheel) | 3.14.4 | 1.0.0rc1 | 6.9.0 | 4.4.0 | 192 passed, 1 skipped |
| Floor boundary (wheel) | 3.11.9 | 1.0.0rc1 | 5.18.0 | 3.1.0 | 192 passed, 1 skipped; `pip check` clean |

Declared ranges follow the evidence: Python `>=3.11` (3.10 not tested →
narrowed), CE `>=1.0.0rc1,<2` (older CE required the removed bridges),
plotly `>=5.18`, dash `>=3.1`.

## Dependency and security review

`pip-audit --strict` (2026-07-16): newest-boundary set — no known
vulnerabilities; floor set with dash 3.1.0 + Flask 3.1.3 + Werkzeug 3.1.8 —
no known vulnerabilities. dash 2.14 (previous floor) carries PYSEC-2024-35
and pins vulnerable Flask/Werkzeug (<3.1); floor raised to `>=3.1`
accordingly. This is a point-in-time scan, not a certification.
Maintenance risks: Plotly major releases (5→6 already absorbed), Dash major
churn confined to the optional `[live]` extra, upstream CE PlotSpec changes
guarded by the parity suite. No kaleido/image-export dependency: image
export is out of scope.

## Known limitations / nonblocking backlog

- No dedicated multiclass tests (documented as ⚠️ in the support matrix).
- `instance_explorer` is hover-only v1; drill-down deferred by design.
- Dashboard style is registry-validated (not smoke-rendered) in the wheel
  gate; its runtime is covered by the package test suite.
- Parity tests prepend the sibling `calibrated_explanations/src` checkout to
  `sys.path` when present (harmless fallback in CI where it is absent).
- Notebook examples are documentation, not executed in CI.

## Ownership

- Maintainer: Tuwe Löfström <tuwe.lofstrom@ju.se> (`project.maintainers`).
- Support route: public `calibrated_explanations` repository issues;
  security via `SECURITY.md` (private vulnerability reporting).
- Licence: BSD-3-Clause (repository licence).
- PyPI: distribution name `calibrated-explanations-visualization-plotly`
  verified unclaimed on PyPI (2026-07-16). To be claimed via a *pending
  publisher* bound to this repository's `release-pypi.yml` workflow under
  the CE maintainer account **before** the first release tag, per
  `docs/maintainer-release.md`. Not published as part of this review.
