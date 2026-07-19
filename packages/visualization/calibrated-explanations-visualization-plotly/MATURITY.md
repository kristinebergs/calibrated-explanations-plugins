# Maturity evidence — calibrated-explanations-visualization-plotly

## 0.3.2 re-audit — status set to `experimental` (2026-07-19)

Full skeptical re-audit at commit `f4b9a2b` treating the previous `mature`
label, classifiers, and all prior evidence as untrusted claims. The code and
test evidence below now satisfies the technical promotion criteria, but the
lifecycle status is deliberately **demoted to `experimental`** because the
publication criteria cannot be satisfied from the repository alone:

**Blocking (human actions outside the repo):**

1. PyPI name `calibrated-explanations-visualization-plotly` is unclaimed —
   verified `HTTP 404` from `pypi.org/pypi/<name>/json` on 2026-07-19. The
   pending publisher bound to `.github/workflows/release-pypi.yml` (which
   correctly uses `environment: pypi` + `id-token: write` OIDC publishing)
   must be created under the maintainer account before the first tag.
2. No release exists, so the documented install command has never been
   verified against a real distribution; README now avoids presenting it as
   usable.
3. Continuous two-boundary CI (3.11 + 3.14, added to `ci.yml` this audit)
   has not yet run on GitHub-hosted runners.
4. Maintainer acceptance of the re-audited scope (this document) is pending
   explicit sign-off.

When 1–4 complete, re-promotion needs a maturity-promotion PR flipping
`status` and the classifier back, plus a clean-environment install check
from PyPI; the metapackage curation decision remains separate.

**Defects found and fixed in this re-audit** (all previously hidden behind
the `mature` label):

- **Alternative ranking diverged from CE** (parity ledger BARS-004): the
  inline `_rank_items` scored ensured ranking as `w·p + (1−w)·width`
  (preferring *wide* intervals) where CE's `calculate_metrics` scores
  `(1−w)·(1−width) + w·p` (preferring *narrow* ones); the classification
  flip fired at `base < 0.5` where CE flips at `base ≤ 0.5`; identical-to-
  base rows used a 1e-10 cutoff where CE uses `np.isclose`. `_rank_items`
  now calls CE's public `rank_features`/`calculate_metrics` (no replica);
  `factual_bars._compute_ranking`'s silent inline-replica fallback was
  removed the same way. Evidence:
  `tests/parity/test_alternative_ranking_parity.py` (13 hand-computed
  oracle cases) plus updated `test_alternative_bars.py` fixtures.
- **Factual bar colours were wrong** (BARS-017): tab:red/tab:blue
  (`#d62728`/`#1f77b4`) instead of the mpl adapter's `red`/`blue`
  (`#ff0000`/`#0000ff`); interval overlays used alpha 0.40 vs CE's 0.20.
  Corrected; parity tests compare against exported mpl primitives.
- **Threshold/caption strings diverged** (BARS-021): uppercase `P(Y…)`,
  wrong precision, wrong binary fallback (`P(Y!=1)` vs CE's `P(y=0)`), and
  no interval-threshold `y_hat` format. The caption block now mirrors CE
  `plotting.py` branch-for-branch, with unit tests per branch.
- **`show_uncertainty` no-op** (BARS-025): now warns visibly (UserWarning +
  INFO) instead of being silently accepted.
- **Component metadata was wrong**: all 16 builders/renderers declared
  `capabilities: ["plot:renderer"]` (builders now `plot:builder`, matching
  CE builtins vocabulary); `plugin_meta["version"]` reported artifact-schema
  versions (0.1.0/0.2.0) instead of the distribution version; provider
  `plotly.local`/`plotly.global`/`plotly.dashboard` implied a Plotly-org
  identity (now `calibrated-explanations-plugins` from `_version.py`).
  `tests/test_package_contract.py` now runs every entry-point component
  through CE's public `validate_plugin_meta` +
  `validate_plot_builder_metadata`/`validate_plot_renderer_metadata` and
  fails on any version/capability/provider drift.
- **Import side effects removed**: importing `ce_visualization_plotly` (or
  `.plugin`) no longer registers styles or monkey-patches CE.
  `register_plotly_visualization_components()` (also exposed as
  `PlotlyVisualizationBootstrap.register()`) is the explicit, idempotent
  entry; `install_compat_bridges=False` opts out of the CE 1.0.x bridges.
  The bridges are version-gated (CE major must be 1) and warn visibly when
  not installed. New test:
  `test_root_import_registers_nothing_and_patches_nothing`.
- **Dependency boundaries corrected**: NumPy (directly imported at runtime)
  is now declared (`>=1.24`, CE's own floor); runtime depends on base
  `calibrated-explanations` (matplotlib was never imported at runtime — the
  `[viz]` extra moved to the new `test` extra used by the parity suite).
- **Multiclass claims made executable**: `tests/test_multiclass.py` runs a
  real 3-class CE workflow through every style claiming limited multiclass
  support (7 tests; one-vs-rest headers assert `P(y=<label>)` captions).
- **Fallback audit**: broad `contextlib.suppress(Exception)`/`except
  Exception` sites narrowed to precise types (metadata probes) or removed
  (ranking); the classification-collection `get_confidence()` probe no
  longer relies on swallowing CE's `AssertionError`. The two notebook
  display probes remain broad by design with justifying comments.
- **Evidence infrastructure**: the wheel gate now smoke-renders the
  dashboard style to standalone HTML (previously registry-validated only);
  `ci.yml` runs changed packages on a {3.11, 3.14} matrix;
  `validate_repo_structure.py` resolves cross-module plugin_meta constants.

**Validation (observed 2026-07-19, dev env Python 3.11.9, CE 1.0.0rc1):**
`ruff check src tests` clean; `python -m pytest -q` 233 passed / 2 skipped
(parity subset: 43 passed / 2 skipped; ranking parity 13 passed; multiclass
7 passed); `validate_repo_structure.py`, `lifecycle.py check`,
`lifecycle.py index --check`, and repo policy tests (29) all pass. Wheel
gate (`scripts/runtime_check_package.py`, fresh venv, CE from PyPI): exit 0
— wheel built and installed, `pip check` clean, entry-point discovery and
trust registration validated, **all 8 styles smoke-rendered including the
dashboard standalone-HTML path** (new in this audit; previously
registry-validated only), 233 passed / 2 skipped from the **installed
wheel** at 84.35 % coverage, 100 % plugin docstring coverage.
`pip-audit --strict` on the declared dependency set
(CE>=1.0.0rc1,<2 / numpy>=1.24 / plotly>=5.18 / dash>=3.1): no known
vulnerabilities (2026-07-19; point-in-time scan, not a certification).
Registered-styles count unchanged (8 styles + 1 deprecated alias). The
3.11/3.14 boundary-venv runs recorded for 0.3.1 were not repeated for
0.3.2; the new CI matrix supersedes them once it runs on GitHub.

---

## 0.3.1 hardening review (2026-07-18)

Independent re-audit of the 0.3.0 promotion; the `mature` status was treated
as provisional and re-verified. Changes made:

- **Bridge isolation.** All registration-time wrapping of public CE symbols
  (`FactualExplanation.plot`, `AlternativeExplanation.plot`,
  `plotting.plot_global`) moved out of `plugin.py` into one compatibility
  module, `_ce_compat.py`, whose docstring records why each bridge exists,
  the CE range that needs it, and the removal condition. The two chained
  `AlternativeExplanation.plot` wrappers were consolidated into one; the
  `filename=` → `path=` coercion is now uniform across all four bridged local
  styles (previously the feature-summary bridge silently ignored
  `filename=`).
- **Private-member removal.** `alternative_bars` no longer imports
  `viz.builders._legacy_get_fill_color` (CE-private); the inline copy is the
  canonical implementation, and `test_inline_fill_color_matches_ce_legacy_implementation`
  compares it against the CE original (53 probabilities × 4 reductions plus
  both regression constants) as the parity oracle.
- **Role heuristics opt-in.** The ensured plot applied ensured/counterfactual
  role heuristics by default when metadata was absent, contradicting the
  README's opt-in claim. Heuristics now require `infer_roles=True`, never
  override explicit all-False rule metadata, and remain marked
  `role_source="heuristic"`. Default is metadata-or-unknown.
- **factual_simple contract.** One-sided explanations with
  `show_uncertainty=True` now raise `Warning` (previously rendered garbage
  error bars); hover shows the full untruncated rule text via customdata.
- **uncertainty_quadrant contract made precise.** x = |calibrated weight|,
  y = weight-interval width; rules without two-sided intervals are omitted
  with a visible `UserWarning` (previously silent) and an empty result raises
  `ValueError`. README support-matrix row upgraded from blanket ⚠️ to the
  explicit contract.
- **Security fix (standalone dashboard).** The instance-workspace summary
  panel built DOM content via `innerHTML` from unescaped record values
  (true labels / targets are user-controlled), allowing HTML injection from
  hostile class labels at view time. It now builds DOM nodes via
  `textContent` only; `test_dashboard_html_treats_hostile_labels_as_text`
  guards both the escaped JSON channel and the DOM-construction pattern.
- **Installed-wheel test fidelity.** All `sys.path` source-tree hacks were
  removed from the test suite (including the parity tests' sibling
  CE-checkout shadowing). `tests/conftest.py` prefers the installed
  distribution and falls back to `src/` only when no version-matching install
  exists; the wheel gate's coverage target now measures the installed
  package (`--cov=ce_visualization_plotly`).
- **Docs corrected.** README no longer implies CE auto-loads entry points in
  user code (CE 1.0.x loads them only via
  `plugins.registry.load_entrypoint_plugins()`/CLI); the quick-start import
  is documented as required.

Validation (all observed, 2026-07-18): dev suite 201 passed / 1 skipped;
`ruff check src tests` clean; wheel gate
(`scripts/runtime_check_package.py`) exit 0 with 201 passed / 1 skipped from
the installed wheel at 83.75 % coverage and 100 % plugin docstring coverage;
floor boundary venv (py 3.11.9, plotly 5.18.0, dash 3.1.0, CE 1.0.0rc1,
installed wheel, `pip check` clean) and newest boundary venv (py 3.14.4,
plotly 6.9.0, dash 4.4.0, CE 1.0.0rc1) both 201 passed / 1 skipped;
`pip-audit --strict` on the newest closure: no known vulnerabilities;
`validate_repo_structure.py`, `lifecycle.py check`, and
`check_version_bumps.py` all pass. PyPI name re-verified unclaimed
(HTTP 404) on 2026-07-18 — claiming it via the pending-publisher flow bound
to `release-pypi.yml` remains the outstanding human action.

---

# 0.3.0 promotion review

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
