# Lifecycle migration and classification (2026-07-15)

Every existing plugin package was inspected and classified on evidence, per
ADR-P001. Where evidence was insufficient for `mature`, the package was
classified `experimental` — repository presence, prior metapackage membership,
and `0.x` versions were treated as non-evidence in both directions.

Blockers common to **all** packages (each alone rules out `mature`):
no `project.maintainers`; no `project.license`; never published to PyPI
(PyPI-name ownership undecided); no wheel-runtime test evidence recorded
against the maturity checklist.

| Distribution | Family | Proposed status | Was in metapackage | Proposed metapackage | Evidence for classification | Unresolved blockers beyond the common ones |
|---|---|---|---|---|---|---|
| calibrated-explanations-calibration-example | calibration | experimental | yes | no | Example/demo that delegates to CE's legacy calibrator; exists to show wiring, not to provide a method | Would also fail curation rule 7 (examples must not pad metapackages) |
| calibrated-explanations-calibration-idr | calibration | experimental | no | no | README itself states it is "not listed in the official calibration metapackage until dependency, licensing, wheel, and CE integration conformance are proven"; requires Python >=3.13 (conflicts with metapackage `>=3.11`); backend `isodistrreg` installable only from a git commit, not PyPI | PyPI-installable backend; Python-range conflict with family metapackage |
| calibrated-explanations-explanation-alternative-example | explanation | experimental | yes | no | Example/demo delegating to CE legacy plugin | Curation rule 7 |
| calibrated-explanations-explanation-factual-example | explanation | experimental | yes | no | Example/demo delegating to CE legacy plugin | Curation rule 7 |
| calibrated-explanations-explanation-factual-lime | explanation | experimental | yes | no | Real integration but heavy `lime` dependency (unmaintained upstream); no semantic-evidence documentation per explanation-family gates | Dependency maintenance-risk review; family-specific semantic evidence |
| calibrated-explanations-explanation-factual-shap | explanation | experimental | yes | no | Real integration but heavy `shap` dependency; no semantic-evidence documentation | Dependency weight/platform review; family-specific semantic evidence |
| calibrated-explanations-visualization-dashboard | visualization | experimental | no | no | Plotly+matplotlib+kaleido dependency stack; absent from metapackage already; README lacked required sections until this migration | Family-specific visualization gates (headless rendering, encoding docs) |
| calibrated-explanations-visualization-example | visualization | experimental | yes | no | Example/demo delegating to the default PlotSpec builder/renderer | Curation rule 7 |
| calibrated-explanations-visualization-factual-shap | visualization | experimental | no | no | SHAP-dependent visualization; absent from metapackage already | Dependency weight review; visualization gates |
| calibrated-explanations-visualization-plotly | visualization | experimental | yes | no | Most active package (v0.2.x, substantial tests incl. parity suite) — the closest promotion candidate, but 28 parity tests currently fail locally and no maturity evidence has been assembled | Fix/triage parity failures; assemble promotion PR evidence; decide PyPI ownership |

Metapackages (no status by design):

| Distribution | Change |
|---|---|
| calibrated-explanations-calibration | Dependencies emptied (previously curated the example plugin) |
| calibrated-explanations-explanation | Dependencies emptied (previously curated four experimental plugins) |
| calibrated-explanations-visualization | Dependencies emptied (previously curated example + plotly) |
| calibrated-explanations-plugins | Unchanged content: depends on exactly the three family metapackages |

No package was published and no release tag was created during this
migration. Nothing in this table prevents a future promotion; it records why
`mature` could not be claimed today.
