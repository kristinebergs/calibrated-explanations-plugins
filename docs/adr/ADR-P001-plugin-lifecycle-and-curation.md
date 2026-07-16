# ADR-P001: Plugin lifecycle, maturity, and curation

- Status: Accepted (2026-07-15; simplified 2026-07-16)
- Scope: this repository. Upstream CE ADRs 006/013/014/015 govern the runtime
  plugin contract and are unaffected.

## Context

The repository distinguished plugin families but not lifecycle: every package
looked equally official, example plugins padded metapackages, and a correctly
formatted tag was sufficient to publish any package. The first lifecycle
implementation fixed that but grew into a distributed governance framework —
nine scripts, four workflows, and duplicated policy prose — oversized for a
one-to-two-maintainer ecosystem.

## Decision

- Exactly three statuses — `experimental`, `mature`, `deprecated` — declared
  in each plugin's `[tool.ce_plugin_repo] status`. No `candidate` status, no
  `publish` flag, no link to runtime trust (`plugin_meta["trusted"]`).
- Curation is expressed solely as family metapackage dependencies; the
  umbrella depends on exactly the three family metapackages. Empty family
  metapackages are valid in the repository but are not release products.
- Lifecycle is metadata, not location: the `packages/{family}/` layout never
  changes on promotion.
- One command, `scripts/lifecycle.py` (`check`, `list`, `index`, `release`),
  owns discovery, policy validation, the generated package index, and release
  gating. `scripts/validate_repo_structure.py` keeps the structural and
  plugin-contract checks.
- Automation covers only objective gates (metadata, curation, wheel-based
  tests, release eligibility); scientific and semantic judgement stays in the
  promotion PR review. Policy prose lives in `docs/plugin-lifecycle.md` only.

## Consequences

- Publication requires an explicit, reviewed promotion plus the protected
  `pypi` environment; a tag is never sufficient.
- At migration (2026-07-15) every existing plugin was classified experimental
  — none had a maintainer, licence metadata, or wheel-test evidence — and all
  family metapackages were emptied (details in the git history of
  `docs/lifecycle-migration.md`).
- CI validates only changed packages plus repository-wide policy; a full
  mature-package sweep can be added when there are enough mature plugins to
  justify it.
