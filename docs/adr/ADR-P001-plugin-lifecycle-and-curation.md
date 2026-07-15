# ADR-P001: Plugin lifecycle, maturity, curation, and publication model

- Status: Accepted
- Date: 2026-07-15
- Scope: `calibrated-explanations-plugins` repository (repo-local ADR; upstream
  CE ADRs 006/013/014/015 govern the runtime plugin contract and are unchanged)

## Context

The repository distinguished plugin *families* but not plugin *lifecycle*.
Every package looked equally "official": example plugins were metapackage
dependencies, every README advertised `pip install <name>` although nothing is
published, and a correctly formatted tag was sufficient to trigger a PyPI
release for any package. There was no explicit distinction between plugins
being evaluated, plugins fit for publication, plugins recommended by default,
and plugins that should no longer be recommended.

## Decision

### Single source of truth

Each individual plugin package declares its lifecycle state in its own
`pyproject.toml`:

```toml
[tool.ce_plugin_repo]
family = "<calibration|explanation|visualization>"
status = "<experimental|mature|deprecated>"
import_name = "<python import package>"
```

- Exactly three persisted statuses. No `candidate` status: a plugin under
  review stays `experimental` until its promotion PR merges (`candidate` is a
  label/review concept only).
- No independent `publish` flag: PyPI eligibility is derived from `status`.
- Runtime trust metadata (`plugin_meta["trusted"]`) is not read for, and does
  not affect, lifecycle decisions.
- Metapackages declare `family = "meta"` and must not declare a status; their
  content is a curation decision, validated against plugin statuses.
- Curation (the "recommended default installation" set) is expressed solely as
  family metapackage dependencies. No hand-maintained manifest duplicates
  `pyproject.toml` metadata; the package index is generated from it.

### Directory layout unchanged

Lifecycle is metadata, not location. `packages/{calibration,explanation,
visualization,meta}` stays; no `packages/experimental/` or `packages/mature/`
trees, so promotion never moves files or breaks import paths and history.

### Shared discovery

`scripts/repo_packages.py` provides `PackageRecord` (path, distribution name,
version, package type, family, status, import name, requires-python, CE
requirement, maintainers, metapackage membership) and the curation/status
validators. All lifecycle-aware scripts (`validate_repo_structure.py`,
`check_meta_package_sync.py`, `resolve_release_tag.py`,
`list_buildable_packages.py`, `list_official_plugin_packages.py`,
`official_plugins.py`, `generate_package_index.py`,
`check_docs_install_commands.py`, `list_promotion_candidates.py`) consume it
instead of re-scanning packages independently.

### Enforcement points

1. **Structure validation** requires a valid status on every plugin, rejects
   status on metapackages, applies status-sensitive README rules (experimental:
   source install + "not published to PyPI" warning, no bare PyPI command;
   mature: PyPI command + maintainers + licence; deprecated: notice +
   migration guidance), and keeps all previous checks.
2. **Curation validation** enforces: only mature plugins in family
   metapackages, family match, umbrella = exactly the three family
   metapackages, and sampled `requires-python` compatibility via `packaging`
   (CPython 3.8–3.14 minors; exotic specifiers remain manual review).
3. **Release gating** (`resolve_release_tag.py`) rejects experimental
   releases, deprecated releases (unless the maintainer-approved
   `workflow_dispatch` override is used), metapackage releases under curation
   violations, tag/version mismatches, and commits not reachable from
   `origin/main`. Publication continues to use the protected `pypi`
   environment and trusted publishing.
4. **Tiered CI**: all packages get policy + metadata + index validation;
   changed packages get wheel build + runtime + their tests; promotion PRs
   (detected by diffing status against the base ref) additionally run the full
   release-grade suite for the promoted packages; mature packages get
   wheel-runtime validation on every run; metapackage changes get wheelhouse
   build + install + runtime verification of each metapackage environment.

### Migration outcome

All existing plugins were classified **experimental** (see
`docs/lifecycle-migration.md` for the evidence table). No package currently
satisfies the mandatory maturity gates (none declares a maintainer or licence
metadata; none is published). Consequently all family metapackages were
emptied — examples are not kept to make metapackages non-empty — and an empty
family metapackage is explicitly valid.

## Consequences

- Publishing anything now requires an explicit, reviewed promotion; a tag or
  directory presence is never sufficient.
- The repository stops over-claiming: no README or doc advertises PyPI
  availability for unpublished packages, and "official" is reserved for mature
  plugins.
- Promotion is a metadata + evidence change with CODEOWNERS review, not a file
  move.
- The first real promotions (plotly visualization is the closest candidate)
  must supply maintainers, licence metadata, and PyPI-name decisions that are
  currently unresolved.
