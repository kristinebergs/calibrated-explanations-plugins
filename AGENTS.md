# AGENTS.md — calibrated-explanations-plugins

This is the official plugin monorepo for `calibrated-explanations`.
It publishes packages across three families: `calibration`, `explanation`, `visualization`.

## Canonical Upstream Context

The OSS library defines the contracts all plugins must conform to.
Read these before making any changes:

- `../calibrated_explanations/CONTRIBUTOR_INSTRUCTIONS.md` — CE conventions, branching, testing
- `../calibrated_explanations/docs/improvement/adrs/ADR-006-plugin-model.md` — plugin trust model
- `../calibrated_explanations/docs/improvement/adrs/ADR-013-plugin-registry.md` — plugin registry
- `../calibrated_explanations/docs/improvement/adrs/ADR-014-plugin-interface.md` — plugin interface
- `../calibrated_explanations/docs/improvement/adrs/ADR-015-plugin-lazy-import.md` — lazy import pattern

## Repository Structure

```
packages/
├── calibration/   ← calibration family plugins
├── explanation/   ← explanation family plugins
├── visualization/ ← visualization family plugins
└── meta/          ← curated metapackage aggregators
templates/         ← scaffold templates for new plugins
scripts/           ← build, release, lifecycle, registry helpers
tests/             ← lifecycle and governance policy tests
docs/
├── plugin-lifecycle.md            ← lifecycle, maturity, curation, governance
├── adr/ADR-P001-plugin-lifecycle-and-curation.md
├── package-index.md               ← generated; do not edit by hand
├── lifecycle-migration.md
├── public-intake/                 ← staged public contribution route
├── which-package-should-i-install.md
└── maintainer-release.md
```

## Plugin Lifecycle

Every plugin package declares `status = "experimental" | "mature" |
"deprecated"` in `[tool.ce_plugin_repo]` (its `pyproject.toml`). This is the
single source of truth for lifecycle state:

- **experimental** — source-install only; never released to PyPI; never in a
  metapackage; README must warn it is not published to PyPI
- **mature** — passed the maturity review (`docs/plugin-lifecycle.md`);
  releasable to PyPI; requires `project.maintainers` and licence metadata
- **deprecated** — excluded from metapackages and ordinary releases; README
  must carry a deprecation notice and migration guidance

Status changes to `mature` go through a maturity-promotion PR
(`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`). Do not conflate
lifecycle status with runtime trust (`plugin_meta["trusted"]`) — they are
independent concepts. Shared discovery/validation logic lives in
`scripts/repo_packages.py`.

## Plugin Protocol

Every plugin package must:
1. **Extend the correct Protocol class** — no duck typing, no subclassing the base
2. **Register in the family registry** — `calibration.registry`, `explanation.registry`,
   or `visualization.registry`
3. **Use lazy imports** — wrap any optional dependency in `try/except ImportError`
4. **Declare a fallback** — if the optional dependency is missing, the plugin must be
   omitted from the registry entry's `visible` set, not raise at import time
5. **Match CE API version** — check that `CalibrationExplainer._API_VERSION` is compatible

## What Is Official and Curated

The curated (recommended default) plugin sets are the dependencies of the
three family metapackages; CI resolves them from those dependency lists. Only
plugins with `status = "mature"` may appear there, and curation is a separate
review decision from maturity — mature plugins are not added automatically.
Adding a new plugin:
1. Scaffold a package under `packages/<family>/<name>/` (starts `experimental`)
2. Add a registry entry
3. Promote to `mature` via a maturity-promotion PR when the review passes
4. Optionally propose curation: an entry in the family metapackage
   `pyproject.toml` (validated by `scripts/check_meta_package_sync.py`)

## Release Relationship

Plugins are versioned independently from OSS CE.
Release sequence: OSS CE (patch/minor/major) → plugins compatibility check → plugins release.
Coordinate major API changes with the OSS release via the `@release-coordinator` agent.

## Code Generation Rules

- Use conventional commits: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- All public functions and classes need docstrings
- Tests go in `packages/<family>/<name>/tests/`
- New plugins should start from `templates/`; use the `/scaffold-plugin` prompt
