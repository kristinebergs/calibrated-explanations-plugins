<!--
Maturity-promotion pull request.
Use this template when changing a plugin's status from "experimental" to
"mature". Open it with:
  https://github.com/kristinebergs/calibrated-explanations-plugins/compare/main...<branch>?template=maturity_promotion.md
Apply the labels: maturity-review, publication-request
(add metapackage-review only if curation is requested).
-->

# Maturity promotion request

## Identification

- **Distribution name:**
- **Plugin identifier(s)** (`plugin_meta["name"]`):
- **Family:** <!-- calibration | explanation | visualization -->
- **Current status:** `experimental`
- **Proposed status:** `mature`
- **Requested initial PyPI version:**
- **Maintainer** (must match `project.maintainers`):
- **Prior review issue** (public intake issue or internal issue link):

## Compatibility

- **Supported Python versions** (`requires-python`):
- **Supported calibrated-explanations range:**

## Evidence

- **Test evidence** (what is covered; link CI runs):
- **Wheel-runtime evidence** (`python scripts/runtime_check_package.py --package-path packages/<family>/<name>` output or CI link):
- **Documentation status** (README completeness: purpose, configuration, assumptions, limitations, failure modes, support route):
- **Dependency and licence review** (direct runtime dependencies, licences, known vulnerabilities):
- **Known limitations:**
- **PyPI name and ownership status** (available / owned by project / transfer agreed):

## Family-specific scientific / semantic evidence

<!-- Calibration: claimed calibration or interval property, assumptions under
     which it holds, supported modes and tasks, shape/boundary behaviour,
     reproducibility, and at least one test tied to a canonical or
     independently checkable expected result.
     Explanation: exact output semantics, supported modes and tasks,
     uncertainty-semantics preservation, unsupported-input behaviour, and at
     least one independently checkable semantic example.
     Visualization: meaning of each visual encoding, correspondence between
     rendered elements and the PlotSpec/explanation payload, headless
     rendering, missing/extreme/interval-valued inputs, and absence of
     misrepresenting transformations.
     Research-derived plugins: cite the method; separate properties of the
     original method from properties of the CE integration; list assumptions
     not covered by ordinary software tests and deviations from the reference
     implementation. -->

## Metapackage curation

- **Metapackage inclusion requested?** <!-- No is a valid, common answer -->
- **Justification if requested** (dependency weight, platform restrictions,
  Python/CE compatibility, maintenance risk, general usefulness):

<!-- Curation is a separate decision from maturity; prefer a separate PR or at
     least a separate commit for the metapackage dependency change. -->

## Checklist

- [ ] `status = "mature"` set in `[tool.ce_plugin_repo]` (this PR)
- [ ] `project.maintainers` and `project.license` declared
- [ ] README updated: `Status: \`mature\``, PyPI install command, configuration,
      assumptions, limitations, failure modes
- [ ] All mandatory maturity gates in `docs/plugin-lifecycle.md` resolved
- [ ] Lifecycle documentation updated (`python scripts/generate_package_index.py`)
- [ ] Full mature-package validation suite passes in CI (promotion job)
- [ ] No import-time side effects beyond deterministic entry-point registration
- [ ] Explicit approval from the responsible code owner

<!-- Mature status asserts that the plugin passed the repository's maturity
     review; it does not assert universal scientific validity. -->
