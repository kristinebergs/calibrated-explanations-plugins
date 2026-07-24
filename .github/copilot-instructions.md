# GitHub Copilot Instructions — calibrated-explanations-plugins

> **Read `AGENTS.md` at the repo root first.** It is the canonical reference for this
> plugin monorepo: structure, plugin protocol, registry rules, and release relationship.
> This file adds only GitHub Copilot-specific context.

---

## How to Use This Repo with Copilot

- Attach `#AGENTS.md` when starting a new chat session to give Copilot the full plugin context.
- For scaffolding a new plugin, use the `/scaffold-plugin` prompt (see `AGENTS.md`).
- Copilot **will not** automatically follow plugin protocol rules unless the instructions are loaded
  — always reference `AGENTS.md` for contract-sensitive work.

## Scoped Instructions

Copilot applies context automatically based on the file you are editing:

| Editing path | Read first |
|---|---|
| `packages/calibration/**` | `AGENTS.md` + upstream ADR-014 |
| `packages/explanation/**` | `AGENTS.md` + upstream ADR-014 |
| `packages/visualization/**` | `AGENTS.md` + upstream ADR-014 + ADR-015 |
| `templates/**` | `AGENTS.md` (scaffold templates) |

## Plugin Protocol Checklist (Copilot reminder)

Every plugin package must satisfy:

1. Extends the correct Protocol class — no duck typing, no subclassing the base
2. Registered in the family registry (`calibration.registry`, `explanation.registry`, or `visualization.registry`)
3. Uses lazy imports — wraps optional dependencies in `try/except ImportError`
4. Declares a fallback — plugin is omitted from `visible` set when optional dep is missing
5. Matches CE API version — checks `CalibrationExplainer._API_VERSION` compatibility

## Validation

Before proposing a merge:

```bash
ruff check .
pytest -q
```

Run both commands from the affected package directory.

## Key Documentation

| Document | Purpose |
|---|---|
| `AGENTS.md` | Plugin protocol, registry rules, release relationship |
| [Upstream contributor instructions](https://github.com/Moffran/calibrated_explanations/blob/main/CONTRIBUTOR_INSTRUCTIONS.md) | Upstream OSS canonical rules |
| [ADR-006](https://github.com/Moffran/calibrated_explanations/blob/main/development/adrs/ADR-006-plugin-registry-trust-model.md) | Plugin trust model |
| [ADR-013](https://github.com/Moffran/calibrated_explanations/blob/main/development/adrs/ADR-013-interval-calibrator-plugin-strategy.md) | Interval plugin strategy |
| [ADR-015](https://github.com/Moffran/calibrated_explanations/blob/main/development/adrs/ADR-015-explanation-plugin.md) | Explanation plugin architecture |
| [ADR-037](https://github.com/Moffran/calibrated_explanations/blob/main/development/adrs/ADR-037-visualization-extension-and-rendering-governance.md) | Visualization plugin governance |
