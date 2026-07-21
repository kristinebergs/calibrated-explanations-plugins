# Maturity evidence — calibrated-explanations-visualization-plotly

## Curation into the visualization family metapackage, version 0.3.5 (2026-07-21)

`calibrated-explanations-visualization-plotly==0.3.4` (below) was confirmed
published on PyPI (`https://pypi.org/pypi/calibrated-explanations-visualization-plotly/json`,
release date 2026-07-20), resolving the sole blocker the 0.3.4 entry recorded
against curation ("resolvable from PyPI"). This package is now added to
`packages/meta/calibrated-explanations-visualization`'s dependencies
(`>=0.3.5,<0.4`, base install) and its `[live]` optional-dependency extra
(`calibrated-explanations-visualization-plotly[live]>=0.3.5,<0.4`) — curation
never adds `dash` directly to the metapackage; the Plotly plugin's own
`[live]` extra remains the sole owner of that dependency contract.

Bumped `0.3.4` → `0.3.5` (mirrored in `_version.PACKAGE_VERSION`) because
correcting this package's own now-stale `[tool.ce_plugin_repo]` pyproject.toml
comment ("Curation into the visualization metapackage remains a separate,
later decision pending this package's own PyPI release") is a material
`pyproject.toml` change under `scripts/check_version_bumps.py`, which does
not distinguish comment-only edits from code changes. The correction itself
was necessary: the comment was a factually stale statement this task's
"reconcile stale repository metadata" requirement covers, not optional
cleanup. README's promotion blockquote and installation section (which still
said "the PyPI distribution does not exist yet") were corrected the same way,
without triggering the gate a second time (README.md changes are not
"material" under `check_version_bumps.py`).

Re-verified after the bump:

```text
ruff check packages/visualization/calibrated-explanations-visualization-plotly  -> All checks passed
python -m pytest -q (package suite)                                            -> 254 passed, 2 skipped
python scripts/validate_repo_structure.py                                      -> passed
python scripts/lifecycle.py check                                              -> passed
python scripts/lifecycle.py index --check                                     -> up to date (plugin now listed under
                                                                                    "Mature curated plugins")
```

**Release sequencing implication:** `calibrated-explanations-visualization-plotly`
`0.3.5` must be tagged, built, and published to PyPI *before*
`calibrated-explanations-visualization` `0.3.0` (which now depends on
`>=0.3.5,<0.4`) is published — otherwise the metapackage's dependency floor
would not resolve. See `docs/maintainer-release.md` for the tag-and-publish
sequence; this remains a human release action outside this session's
authorization.

---

## Promotion to `mature`, version 0.3.4 (2026-07-21)

`status` flipped from `"experimental"` to `"mature"` in `[tool.ce_plugin_repo]`
(`pyproject.toml`), version bumped `0.3.3` → `0.3.4` (mirrored in
`_version.PACKAGE_VERSION`; the flip itself is a "material" pyproject.toml
change under `check_version_bumps.py`, so it requires its own bump even
though no other code changed). Classifier updated
`"Development Status :: 4 - Beta"` → `"Development Status :: 5 -
Production/Stable"` — there is no other `mature` plugin anywhere in this
repository yet to follow a precedent from; this is a judgement call for
reviewer sign-off, not a policy-enforced value (`validate_repo_structure.py`
and `scripts/lifecycle.py` do not check classifiers).

**Basis for promotion** — every criterion in `docs/plugin-lifecycle.md`'s
"Mature" definition that is repository-verifiable:

- Named maintainer (`project.maintainers`) and licence (`BSD-3-Clause`)
  declared.
- Declared runtime dependencies and documented Python/CE compatibility
  (`>=1.0.0rc2,<2`, verified against the real PyPI release — see the
  2026-07-20 sections below).
- README covers purpose, installation, configuration, limitations, support.
- Tests pass from a built wheel: `python scripts/runtime_check_package.py
  --package-path packages/visualization/calibrated-explanations-visualization-plotly`
  — exit 0 against real PyPI `1.0.0rc2` (see below).
- No known use of undocumented private CE APIs: static AST audit
  (`tests/test_public_api_boundary.py`) plus manual review, both recorded
  above; human-review box checked.
- Explicit PyPI name-ownership decision: pending publisher configured by the
  maintainer (human action, tracked outside this file).

**Repository-side gates re-verified against this promotion commit:**

```text
ruff check packages/visualization/calibrated-explanations-visualization-plotly  -> All checks passed
python -m pytest -q (package suite)                                            -> 254 passed, 2 skipped
python scripts/validate_repo_structure.py                                      -> passed (README "Status: `mature`"
                                                                                    + bare `pip install` line now present,
                                                                                    both required once status = mature)
python scripts/lifecycle.py check                                              -> passed
python scripts/lifecycle.py index --check                                     -> up to date (plugin now listed under
                                                                                    "Mature standalone plugins")
python scripts/check_version_bumps.py --base <main-tip> <pkg>                  -> passed
python scripts/lifecycle.py release --tag pkg/calibrated-explanations-visualization-plotly/v0.3.4 \
       --default-branch origin/main                                           -> resolved cleanly (distribution name,
                                                                                    package path/type, version match)
```

**Curation status:** deliberately still deferred. This package is not added
to `packages/meta/calibrated-explanations-visualization`'s dependencies —
per `docs/plugin-lifecycle.md`, curation is a separate decision from
promotion, and the metapackage policy requires a curated dependency to be
"resolvable from PyPI," which this package is not yet (its own release tag
has not been pushed).

**Outstanding human actions, unchanged from the checklist below except item
1 (PyPI name ownership), which is in progress separately:**

1. PyPI pending publisher configuration — in progress (maintainer working on
   this now, per the promotion request).
2. GitHub-hosted CI green on this exact promotion commit (the CI run that
   passed previously was for the pre-promotion state; the status/version
   changes here have not yet been through CI).
3. This PR/commit reviewed and merged to `main`.
4. Only after merge: tag `pkg/calibrated-explanations-visualization-plotly/v0.3.4`
   on the merged commit and push it, per `docs/maintainer-release.md`, to
   trigger the real build-validate-publish workflow.
5. Post-publish smoke test (fresh venv, `pip install
   calibrated-explanations-visualization-plotly`, import + register + render
   one style) — to be recorded here once step 4 completes.

---

## Version bump to 0.3.3 — CI policy fix (2026-07-20, later still)

Pushing this branch surfaced a real CI failure independent of everything
above: `scripts/check_version_bumps.py` (repository policy, not part of this
package's own gates) correctly flagged that both this package and
`packages/meta/calibrated-explanations-visualization` changed materially
against `main` (`f4f7cc84561b032bbc01034f4056543f4bd438b1`) without a version
bump. Fixed by bumping `project.version` (and the mirrored
`_version.PACKAGE_VERSION`) to `0.3.3` for this package and to `0.2.2` for the
metapackage, then regenerating `docs/package-index.md`
(`scripts/lifecycle.py index`). Re-verified locally against the real base:
`check_version_bumps.py`, `lifecycle.py check`, `lifecycle.py index --check`,
`validate_repo_structure.py`, `ruff check`, and the full package test suite
(254 passed / 2 skipped) all pass. All version references in the sections
below predate this bump and were written when the package version was still
`0.3.2` — the bump is a version-string-only change with no behavioural
effect, so that evidence remains valid as written.

## CE 1.0.0rc2 published to PyPI — real-release verification (2026-07-20, later same day)

The section below ("RC2 no-bridge adoption re-audit") was written earlier the
same day and correctly reported, as verified fact at that time, that
`calibrated-explanations==1.0.0rc2` did not exist on PyPI or as any tagged
release — that section's dynamic evidence was gathered against a `--no-deps`
substitute wheel for exactly that reason. Later the same day,
`calibrated-explanations==1.0.0rc2` was published to PyPI. This section
re-verifies the primary blocker's resolution against the **real, unmodified**
release, superseding (not replacing — left intact below for the audit trail)
the substitute-wheel evidence.

**Verification performed independently, not taken on assertion:**

```text
python -c "import urllib.request, json; \
  print(sorted(json.load(urllib.request.urlopen( \
    'https://pypi.org/pypi/calibrated-explanations/json'))['releases'].keys())[-3:])"
-> ['1.0.0rc1', '1.0.0rc2', ...checked full list, no other post-rc1 entries]
```

### Real-release compatibility matrix (supersedes the substitute-wheel matrix below)

All three environments rebuilt from scratch, installing `calibrated-
explanations[viz]>=1.0.0rc2,<2` (and, for the base-install row, bare
`calibrated-explanations>=1.0.0rc2,<2` via this package's own declared
dependency) **directly from PyPI, no workarounds**:

| Environment | Python | CE (PyPI) | plotly | numpy | `pip check` | Result |
|---|---|---|---|---|---|---|
| Floor boundary | 3.11.9 | `1.0.0rc2` | 6.7.0 (resolved) | 2.4.6 | clean | 253 passed, 3 skipped, 86.08% cov |
| Newest boundary | 3.14.4 | `1.0.0rc2` | 6.9.0 | 2.5.1 | clean | 253 passed, 3 skipped |
| Base install (no `[live]`) | 3.11.9 | `1.0.0rc2` | 6.7.0 | 2.4.6 | clean | Dash confirmed absent; `factual_bars` renders through the real public API; `launch_instance_workspace(...)` raises the same actionable `RuntimeError` |

`pip-audit` (not `--strict`, since this unreleased package itself is
correctly unauditable from PyPI and `--strict` treats that as fatal): **no
known vulnerabilities** in any real dependency (plotly, numpy, or their
transitive closure) in either environment, after upgrading the venvs' own
bootstrap `pip`/`setuptools` (the only flagged CVEs, and not declared
dependencies of this package).

**The authoritative release gate now passes for real:**

```text
python scripts/runtime_check_package.py \
  --package-path packages/visualization/calibrated-explanations-visualization-plotly
```

Exit 0. Wheel built and installed into a fresh venv with CE pulled from real
PyPI (`>=1.0.0rc2,<2` resolves to `1.0.0rc2`, no substitution); `pip check`
clean; all 8 styles smoke-rendered through public CE APIs including the
dashboard standalone-HTML path; 253 passed / 3 skipped from the installed
wheel at 85.93% coverage; 100% plugin docstring coverage.

### Effect on the promotion decision

Blocker #1 from the section below ("CE 1.0.0rc2 must be tagged and
published") is **resolved**, verified independently. Blockers #3–#5 are
**not** resolved by this event and still require action outside this
session's authorization:

- GitHub-hosted CI has still not been run on this branch (not pushed).
- The PyPI pending publisher for **this package's own** distribution
  (`calibrated-explanations-visualization-plotly`) is still not configured;
  the name is still unclaimed (re-verify before publishing).
- Maintainer sign-off on the documented scope is still outstanding.

**Status remains `experimental`** pending those three. See "Promotion
decision" in the section below for the full checklist, now with item 1
crossed off.

---

## RC2 no-bridge adoption re-audit — status remains `experimental` (2026-07-20)

Skeptical re-audit performed on branch `tmp/no-bridge-proof`, treating every
prior maturity claim (including the "technical promotion criteria satisfied"
language in the 2026-07-19 entry below) as unverified until reproduced. Parent
commit `e72e67c` (merge of `origin/main` `f4f7cc8` into this branch); this
audit's own changes land in the commit(s) that include this file — see `git
log` for the exact SHA, since it cannot be self-referential.

**Environment at audit time:** Python 3.11.9 (dev), Python 3.14.4 (newest
boundary venv, interpreter discovered at
`AppData/Local/Python/pythoncore-3.14-64`). Package version: `0.3.2`
(unchanged — no functional release is being cut this audit; see "Promotion
decision" below for why).

### The central finding: CE 1.0.0rc2 does not exist as an installable artifact

This package's entire promotion premise is that `calibrated-explanations`
gained a native third-party plot-dispatch contract in `1.0.0rc2`, removing the
need for `_ce_compat`'s monkey-patch bridges. That CE-side fix is real and
verified (see CE's own
`development/capabilities/evidence/evidence_plot_plugin_dispatch_v1.0.0rc2.md`,
merged into `Moffran/calibrated_explanations` at commit `5bfeae85`/`e7b5c836`)
— but **`calibrated-explanations==1.0.0rc2` has never been tagged or published
anywhere**:

- PyPI's latest published version is `1.0.0rc1` (verified via
  `https://pypi.org/pypi/calibrated-explanations/json` on 2026-07-20; full
  release list checked, no `1.0.0rc2`, no `1.0.0` final).
- The CE repository's own `pyproject.toml` still declares `version =
  "1.0.0-dev"` at the commit containing the fix; no `v1.0.0rc2` tag exists on
  `Moffran/calibrated_explanations` (the authoritative release repository) as
  of this audit.
- CE's own release plan (`development/current-work/v1.0.0-rc2_plan.md`) lists
  "Tag and publish" and "Full CI matrix green on the exact pushed candidate
  commit" as still-open checklist items, not completed ones.

**Consequence, demonstrated executably, not asserted:** running the real
installed-wheel gate against actual PyPI —

```text
python scripts/runtime_check_package.py \
  --package-path packages/visualization/calibrated-explanations-visualization-plotly
```

— fails with `ERROR: Could not find a version that satisfies the requirement
calibrated-explanations<2,>=1.0.0rc2 ... No matching distribution found for
calibrated-explanations<2,>=1.0.0rc2` (full log retained in session
scratchpad). This is not a defect in this package's declared floor — Phase 3's
non-negotiable requirement (`>=1.0.0rc2,<2`) is the *correct* contract once CE
publishes it — but it means **the installed-wheel gate cannot pass against
PyPI today, and will not until CE ships the release**. Declaring this package
mature while its primary compatibility gate is unsatisfiable from PyPI would
be exactly the kind of exaggerated claim this audit is required to catch.

### What was verified instead, and how

Since no real `1.0.0rc2` artifact exists, dynamic verification used a wheel
built directly from the CE source that implements the fix
(`Moffran/calibrated_explanations` at commit `e7b5c836`, editable checkout at
`C:\Users\loftuw\Documents\Github\moffran\calibrated_explanations`, built via
`python -m build --wheel`; the resulting artifact self-identifies as
`calibrated_explanations-1.0.0.dev0` because that is the source tree's actual
`pyproject.toml` version — the release-preflight tooling that stamps the real
`rc2` string has deliberately not been run, per CE's own release process).
This wheel was installed with `pip install --no-deps` (bypassing the
unresolvable version constraint, since PyPI has nothing to resolve it to) into
three clean virtual environments together with this package's own
freshly-built wheel. Every environment below shows `pip check` reporting the
*exact* expected mismatch:

```text
calibrated-explanations-visualization-plotly 0.3.2 has requirement
calibrated-explanations<2,>=1.0.0rc2, but you have calibrated-explanations
1.0.0.dev0.
```

This is reported here, not hidden — it is proof that the version-string gate
correctly fires, while the tests below prove the *behavioural* contract
(native dispatch, no bridge) genuinely holds against the code that will become
`1.0.0rc2`.

### Compatibility matrix (this audit, 2026-07-20)

| Environment | Python | CE (source) | plotly | dash | numpy | Result |
|---|---|---|---|---|---|---|
| Floor boundary | 3.11.9 | `1.0.0.dev0` @ `e7b5c836` (no-deps wheel) | 5.18.0 | 3.1.0 | 2.4.6 | 253 passed, 3 skipped, 86.08% cov; `pip-audit --strict` clean (after upgrading the venv's own pip/setuptools — those two, not this package's deps, were the only flagged CVEs) |
| Newest boundary | 3.14.4 | `1.0.0.dev0` @ `e7b5c836` (no-deps wheel) | 6.9.0 | 4.4.0 | 2.5.1 | 253 passed, 3 skipped, 86.08% cov; `pip-audit --strict` clean |
| Base install (no `[live]`) | 3.11.9 | `1.0.0.dev0` @ `e7b5c836` (no-deps wheel) | 5.18+ | **absent** | 2.4.6 | 209 passed, 2 skipped (viz-parity and live-dashboard tests requiring matplotlib/dash skip cleanly); Dash import confirmed absent; all non-live styles (factual_bars, alternative_bars, instance_explorer, standalone dashboard) render through the real public CE API; `launch_instance_workspace(...)` raises `RuntimeError: Dash is required for live Plotly dashboards. Install the Plotly visualization package with its live dashboard extra.` |
| Real PyPI (`runtime_check_package.py`, unmodified) | 3.11.9 | attempted `>=1.0.0rc2,<2` from PyPI | — | — | — | **Fails at dependency resolution**, as documented above. This is the authoritative, unmodified release gate — its failure is the accurate signal, not a bug to work around. |

### No-bridge dispatch evidence

`tests/test_no_bridge_proof.py` (new, 14 tests) is the consolidated proof
required by the promotion audit:

- **Symbol-integrity**: `FactualExplanation.plot`, `AlternativeExplanation.plot`,
  `CalibratedExplainer.plot`, `WrapCalibratedExplainer.plot`, and
  `calibrated_explanations.plotting.plot_global` are snapshotted before any
  import and re-asserted identical after package import, plugin-module
  import, entry-point discovery, first registration, repeated registration,
  and after rendering all eight styles through real `CalibratedExplainer`
  objects (not fakes). `_ce_compat.py` is asserted absent both from `src/`
  (static) and from the built wheel's file listing (`zipfile` inspection of a
  freshly built artifact).
- **Dispatch fidelity**: every one of the eight required surfaces (single and
  collection factual `.plot()`, single and collection alternative `.plot()`,
  explainer-level global plotting, standalone-HTML dashboard, repeated
  registration, built-in style after Plotly registration) is exercised
  through CE's real public API with non-default option values
  (`filter_top`, `uncertainty`, `rnk_metric`, `rnk_weight`,
  `include_instance_records`, `aggregate_positions`, `precompute`,
  `available_cards`), asserting on `options_used` echoes, row/record counts,
  and saved-file existence — not just "a figure exists".
- **Negative tests**: an unregistered style raises `ConfigurationError` naming
  the identifier; a typoed kwarg (`filter_tp`) is proven to emit CE's governed
  `UserWarning` at the **collection**-level dispatch path. A companion test
  (`test_typoed_option_on_single_explanation_is_a_known_ce_gap`) documents,
  executably, that the **single-explanation** `.plot()` path currently
  forwards the same typo with *no* warning at all — a real CE-core gap
  (config lives in `plotting.py`'s dispatch machinery, not in this plugin),
  recorded here rather than silently assumed away. See "Known limitations".
- **Built-in-after-Plotly isolation**: `LocalFactualBarsPlotBuilder.build` is
  monkeypatched to raise; CE's own `style="regular"` renders successfully
  without ever touching it.

### Public-API boundary audit (Phase 4)

Static AST scan of every `src/ce_visualization_plotly/*.py` import
(`tests/test_public_api_boundary.py`, new) found and fixed three real
deep-import violations, all now on documented public façades:

| File | Before | After |
|---|---|---|
| `ensured.py` | `calibrated_explanations.utils.helper.calculate_metrics` | `calibrated_explanations.utils.calculate_metrics` |
| `ensured.py` | `calibrated_explanations.viz.builders.build_triangular_plotspec` | `calibrated_explanations.viz.build_triangular_plotspec` |
| `alternative_bars.py`, `factual_bars.py` (lazy imports) | `calibrated_explanations.explanations.explanation.CalibratedExplanation` | `calibrated_explanations.explanations.CalibratedExplanation` |

Several test files (`test_alternative_bars.py`, `test_instance_workspace.py`,
`test_package_contract.py`) had the same deep-import pattern for identity
checks; fixed the same way (`CalibratedExplainer`/`WrapCalibratedExplainer`
now imported from the top-level `calibrated_explanations` package rather than
`calibrated_explanations.core.*`). `calibrated_explanations.plotting` remains
imported in tests only, for the documented `plot_global` identity check — it
is the module CE's own contributor docs name explicitly
(`docs/contributor/plugin-contract.md`) for this purpose, so it is treated as
a documented (if not top-level-re-exported) surface for that narrow use.

The inline colour specification in `alternative_bars.py` (`_ce_fill_color`)
was already plugin-owned (not a CE import) from the prior audit, but its
*only* correctness oracle was a diagnostic comparison against CE's private
`viz.builders._legacy_get_fill_color`, which would silently stop testing
anything if CE ever removed that symbol. Added
`test_fill_color_matches_golden_values` (hardcoded expected hex outputs for
nine representative probabilities plus both regression constants) as the
required, non-CE-dependent oracle; the CE-comparison test is retained,
renamed to `..._diagnostic`, and documented as optional. Also added exact
colour/opacity golden-value tests for `factual_bars.py` (`#ff0000`/`#0000ff`
classification/regression bar colours, `rgba(0,0,0,0.20)` uncertainty overlay)
and a static guard (`test_no_source_string_implies_causal_interpretation`)
that no source string uses causal language ("causes", "leads to", "due to",
"results in") for predictive-movement descriptions.

### Compatibility architecture removal (Phase 2)

- `src/ce_visualization_plotly/_ce_compat.py` **deleted** (`git rm`), not just
  unreferenced.
- `install_compat_bridges` parameter **removed entirely** from
  `PlotlyVisualizationBootstrap.register()` and
  `register_plotly_visualization_components()` — not kept as a deprecated
  no-op, since this package has never been released and there is no
  compatibility need to preserve.
- All bridge-marker assertions (`_factual_bars_bridge`,
  `_alternative_bars_bridge`, `_plotly_bridge_version`) replaced with direct
  callable-identity assertions, which is strictly stronger evidence.
- Eight example notebooks were **actually re-executed** (`jupyter nbconvert
  --execute`) against the RC2-dispatch CE source, not merely inspected:
  `local_alternative_bars`, `local_factual_bars`, `local_factual_simple`,
  `global_instance_explorer`, `local_alternative_feature_summary`,
  `local_ensured_plotly`, `local_uncertainty_quadrant`, and
  `dashboard_instance_workspace_standalone`. This surfaced and fixed real,
  independent bugs predating this audit, unrelated to the bridge removal
  itself:
  - Three notebooks imported `ce_visualization_plotly.plugin` but never
    called `register_plotly_visualization_components()` — the import-only
    comment ("registers Plotly styles") was simply wrong, since this package
    deliberately has no import-time side effects. Fixed by adding the
    explicit call.
  - `global_instance_explorer.ipynb` never imported the plugin at all and
    would have raised `ConfigurationError` on first run.
  - Two notebooks (`local_alternative_feature_summary`, `local_ensured_plotly`)
    had a broken dev-convenience cell that popped modules from
    `sys.modules` and then called `importlib.reload()` on them — which raises
    `ImportError: module ... not in sys.modules`. Replaced with the same
    plain import+register pattern used elsewhere (registration is already
    idempotent, so the reload dance was unnecessary).
  - Two notebooks had a stale, factually incorrect comment ("Importing the
    package registers its Plotly styles with calibrated-explanations")
    surviving from before import-side-effect removal; corrected/removed.
  - Five notebooks had an *active* (uncommented) `pip install -e .` cell that
    now fails for the same PyPI-resolution reason described above; commented
    out with an explanatory note, matching the pattern three other notebooks
    already used.
  `dashboard_instance_workspace_live.ipynb` (launches a blocking live Dash
  server) was fixed structurally (register call restored, stale comment
  removed) but **not** re-executed via `nbconvert`, since doing so would hang
  on the live server; this remains a documented, deliberate gap.

### Repository gates (this audit, 2026-07-20)

All run and observed directly, not carried over from a prior claim:

```text
ruff check packages/visualization/calibrated-explanations-visualization-plotly    -> All checks passed
python scripts/validate_repo_structure.py                                        -> passed
python scripts/lifecycle.py check                                                -> passed
python scripts/lifecycle.py index --check                                       -> up to date
python scripts/check_version_bumps.py --base 681894d <pkg>                      -> passed
python -m pytest tests -q            (repo policy tests)                        -> 29 passed
python -m pytest -q                   (package suite, dev env)                   -> 254 passed, 2 skipped
```

Plugin entry-point docstring coverage: **100%** (`plugin.py`, computed via
`scripts.runtime_check_package.plugin_docstring_coverage`).

**Not run this audit:** GitHub-hosted CI. This branch has not been pushed;
doing so was outside this session's authorization, and — per the central
finding above — the `changed-packages` CI job would fail identically to the
local `runtime_check_package.py` run, since GitHub-hosted runners resolve
dependencies from the same public PyPI index. Pushing and observing a red CI
run would not add new information beyond what is already documented here;
getting it to go *green* requires the upstream CE release, not a CI
configuration change.

### Known limitations (new, this audit)

1. **CE 1.0.0rc2 is unreleased.** This is the primary blocker; see above.
2. **Single-explanation typo warnings**: CE's collection-level `.plot()`
   warns on unrecognised kwargs; the single indexed explanation's `.plot()`
   does not (executable proof:
   `test_typoed_option_on_single_explanation_is_a_known_ce_gap`). This is a
   CE-core gap, not fixable from this plugin.
3. **Live dashboard notebook not executed** this audit (see above).
4. PyPI name `calibrated-explanations-visualization-plotly` still unclaimed
   (re-verified `HTTP 404` on 2026-07-20); no pending publisher configured.
5. Carried over from prior audits, still true: `instance_explorer` is
   hover-only; multiclass is one-vs-rest only; no image/PNG export.

### Promotion decision

**Status remains `experimental`.** The repository-controlled technical work
(no-bridge dispatch, public-API boundary, golden-value semantic tests,
three-environment compatibility matrix, all local gates) is complete and
green. Flipping to `mature` is blocked entirely by human/upstream actions this
agent cannot perform or fabricate:

1. ~~`calibrated-explanations` `1.0.0rc2` must be tagged and published to
   PyPI~~ — **done**, verified independently; see the dated section at the
   top of this file.
2. ~~Once published, re-run the **unmodified**
   `scripts/runtime_check_package.py` against the real PyPI artifact and
   confirm exit 0~~ — **done**, exit 0, see top section (253 passed / 3
   skipped, 85.93% cov, `pip check` clean against real `1.0.0rc2`).
3. Push this branch (or its successor) and obtain a green GitHub-hosted CI run
   on the actual `{3.11, 3.14}` matrix — required per
   `docs/plugin-lifecycle.md`; local success does not substitute. **Still
   outstanding.**
4. Configure the PyPI pending publisher for the exact distribution/
   repository/workflow/environment (`docs/maintainer-release.md`). **Still
   outstanding** — name still unclaimed as of this audit.
5. Maintainer sign-off on the documented scope (this file + README). **Still
   outstanding.**

No PyPI ownership, CI execution, or maintainer approval is claimed or
fabricated here. Items 1–2 are now genuinely satisfied; items 3–5 remain the
sole blockers. When they are complete, promotion is a maturity-promotion PR
per the template, plus a version bump to the next unused patch (`0.3.3`) —
metapackage curation stays a separate, later decision per
`docs/plugin-lifecycle.md`.

---

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
