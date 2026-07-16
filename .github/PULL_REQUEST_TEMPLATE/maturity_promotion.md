<!-- Maturity promotion: experimental -> mature. Policy: docs/plugin-lifecycle.md.
     No separate issue is needed for a plugin already in this repository. -->

# Maturity promotion: <distribution-name>

- **Family:** <!-- calibration | explanation | visualization -->
- **Maintainer** (matches `project.maintainers`):
- **Public intake issue** (link if one exists):

## Checklist

- [ ] `status = "mature"` set in `[tool.ce_plugin_repo]`
- [ ] Maintainer and licence declared in `pyproject.toml`
- [ ] Wheel tests pass in CI
      (`python scripts/runtime_check_package.py --package-path <pkg>`)
- [ ] Public CE APIs only — no undocumented private members
- [ ] Python and calibrated-explanations compatibility documented
- [ ] Assumptions and limitations documented honestly in the README
- [ ] Family-specific semantic evidence summarized below
- [ ] Direct dependencies reviewed (weight, maintenance, licences)
- [ ] PyPI name ownership decided (available / project-owned / transfer agreed)
- [ ] Package index regenerated (`python scripts/lifecycle.py index`)
- [ ] Curation requested: **yes / no** — short justification below if yes

## Semantic evidence

<!-- Brief family guidance:
     calibration — the claimed calibration/interval property, its assumptions,
       and one independently checkable expected result;
     explanation — exact output semantics, uncertainty preservation, and one
       checkable semantic example;
     visualization — meaning of each encoding, correspondence to the
       PlotSpec/explanation payload, headless rendering. -->

## Reviewer questions (human judgement, not automated)

- Does the plugin use only supported CE interfaces?
- Do its outputs preserve the semantics it claims?
- Are its assumptions and limitations stated honestly?
- Are its dependencies acceptable?
- Is the PyPI name controlled or available?
- Is there a credible maintainer?

<!-- Mature means "maintained and release-ready within documented scope",
     not universal scientific validity. -->
