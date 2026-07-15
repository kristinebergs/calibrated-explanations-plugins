# Security policy

## Reporting a vulnerability

Please do not open public issues for security problems in plugin packages or
in the release automation.

- Preferred: use GitHub private vulnerability reporting on the public
  `calibrated_explanations` repository
  (<https://github.com/kristinebergs/calibrated_explanations/security>), and
  state that the report concerns a plugin package.
- Alternative: contact the maintainer listed in `.github/CODEOWNERS`.

## Handling

- A critical vulnerability in a **mature** plugin or its direct dependencies is
  grounds for an expedited fix release or, when no fix is available,
  deprecation and yanking of affected PyPI releases.
- A **deprecated** plugin may receive an exceptional security release only
  through the maintainer-approved `workflow_dispatch` override on the release
  workflow (see `docs/plugin-lifecycle.md`).
- Experimental plugins are unpublished; issues in them are fixed in-tree.
