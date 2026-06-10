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
└── meta/          ← metapackage aggregators
templates/         ← scaffold templates for new plugins
scripts/           ← build, release, registry helpers
docs/
├── package-index.md
├── which-package-should-i-install.md
└── maintainer-release.md
```

## Plugin Protocol

Every plugin package must:
1. **Extend the correct Protocol class** — no duck typing, no subclassing the base
2. **Register in the family registry** — `calibration.registry`, `explanation.registry`,
   or `visualization.registry`
3. **Use lazy imports** — wrap any optional dependency in `try/except ImportError`
4. **Declare a fallback** — if the optional dependency is missing, the plugin must be
   omitted from the registry entry's `visible` set, not raise at import time
5. **Match CE API version** — check that `CalibrationExplainer._API_VERSION` is compatible

## What Is Official

Official plugins are declared as dependencies of the three family metapackages only.
CI resolves them at runtime from those dependency lists. Adding a plugin requires:
1. A package under `packages/<family>/<name>/`
2. A registry entry
3. An entry in the family metapackage `pyproject.toml`

## Release Relationship

Plugins are versioned independently from OSS CE.
Release sequence: OSS CE (patch/minor/major) → plugins compatibility check → plugins release.
Coordinate major API changes with the OSS release via the `@release-coordinator` agent.

## Code Generation Rules

- Use conventional commits: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- All public functions and classes need docstrings
- Tests go in `packages/<family>/<name>/tests/`
- New plugins should start from `templates/`; use the `/scaffold-plugin` prompt
