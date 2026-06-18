# CLAUDE.md — calibrated-explanations-plugins

> **Read `AGENTS.md` at the repo root first.** It is the canonical reference for this
> plugin monorepo: structure, plugin protocol, registry rules, and release relationship.
> This file adds only Claude Code-specific context.

---

## Session Startup

At the start of every Claude Code session on this repo:

1. Read `AGENTS.md` (plugin protocol, registry, release rules).
2. Identify which package family the task touches (`calibration`, `explanation`, `visualization`).
3. Read the relevant upstream ADRs listed in `AGENTS.md` before modifying any plugin contract.
4. Run `pytest -q` in the affected package to establish a baseline before making changes.

## Claude Tool Preferences

| Task | Preferred tool |
|---|---|
| Read a known file | `view` (Read), not `bash cat` |
| Search for a symbol | `grep` / `glob`, not `bash find` / `bash rg` |
| Edit a file | `edit` (atomic, targeted) — avoid whole-file rewrites |
| Run tests/lint | `bash` |

When two or more operations are independent, call them in parallel in a single response.

## Validation

Before proposing a merge, run in the affected package directory:

```bash
ruff check .
pytest -q
```

## Key Documentation

| Document | Purpose |
|---|---|
| `AGENTS.md` | Plugin protocol, registry rules, release relationship |
| `../calibrated_explanations/CONTRIBUTOR_INSTRUCTIONS.md` | Upstream OSS canonical rules |
| `../calibrated_explanations/docs/improvement/adrs/ADR-006-plugin-model.md` | Plugin trust model |
| `../calibrated_explanations/docs/improvement/adrs/ADR-014-plugin-interface.md` | Plugin interface |
