# AGENTS.md — calibrated-explanations-plugins

This is the official plugin monorepo for `calibrated-explanations`.
It contains packages across three families: `calibration`, `explanation`, `visualization`.

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
scripts/           ← lifecycle.py, validate_repo_structure.py, build/test helpers
tests/             ← lifecycle policy tests
docs/
├── plugin-lifecycle.md   ← authoritative lifecycle and curation policy
├── maintainer-release.md ← release commands
├── package-index.md      ← generated; refresh with `python scripts/lifecycle.py index`
└── adr/ADR-P001-plugin-lifecycle-and-curation.md
```

## Plugin Lifecycle

Every plugin declares `status = "experimental" | "mature" | "deprecated"` in
`[tool.ce_plugin_repo]` (its `pyproject.toml`) — the single source of truth
for lifecycle state. Curation (the recommended default set) is defined solely
by family metapackage dependencies, which may contain only mature plugins of
their own family. Semantics, gates, and the promotion process:
`docs/plugin-lifecycle.md`. Do not conflate lifecycle status with runtime
trust (`plugin_meta["trusted"]`) — they are independent.

All lifecycle tooling is one command:

```bash
python scripts/lifecycle.py check           # statuses, family placement, curation
python scripts/lifecycle.py list [--type plugin] [--status mature] [--curated]
python scripts/lifecycle.py index [--check] # docs/package-index.md
python scripts/lifecycle.py release --tag pkg/<name>/v<version> [--default-branch origin/main]
```

`scripts/validate_repo_structure.py` owns the structural and plugin-contract
checks (entry points, plugin_meta, README/status consistency).

## Plugin Protocol

Every plugin package must:
1. **Extend the correct Protocol class** — no duck typing, no subclassing the base
2. **Register in the family registry** — `calibration.registry`, `explanation.registry`,
   or `visualization.registry`
3. **Use lazy imports** — wrap any optional dependency in `try/except ImportError`
4. **Declare a fallback** — if the optional dependency is missing, the plugin must be
   omitted from the registry entry's `visible` set, not raise at import time
5. **Match CE API version** — check that `CalibrationExplainer._API_VERSION` is compatible

## Adding a Plugin

1. Scaffold under `packages/<family>/<name>/` with `scripts/scaffold_package.py`
   (always starts `experimental`)
2. Add a registry entry
3. Promote via a maturity-promotion PR
   (`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`) when ready;
   curation into a metapackage is a separate decision that may share the PR
   when justified explicitly

## Release Relationship

Plugins are versioned independently from OSS CE.
Release sequence: OSS CE (patch/minor/major) → plugins compatibility check → plugins release.
Coordinate major API changes with the OSS release via the `@release-coordinator` agent.

## Code Generation Rules

- Use conventional commits: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- All public functions and classes need docstrings
- Tests go in `packages/<family>/<name>/tests/`
- New plugins should start from `templates/`; use the `/scaffold-plugin` prompt
