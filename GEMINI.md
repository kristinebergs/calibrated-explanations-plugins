# GEMINI.md — calibrated-explanations-plugins

> **Read `AGENTS.md` at the repo root first.** It is the canonical reference for this
> plugin monorepo: structure, plugin protocol, registry rules, and release relationship.
> This file adds only Gemini-specific context.

---

## Session Priming

At the start of every Gemini session on this repo:

1. Read `AGENTS.md` (plugin protocol, registry, release rules).
2. Identify which package family the task touches (`calibration`, `explanation`, `visualization`).
3. Read the relevant upstream ADRs listed in `AGENTS.md` before modifying any plugin contract.

## Context Usage

Gemini has a large context window. Use it to include the full source of relevant plugin
modules when answering questions, rather than working from partial snippets.

Gemini does not persist memory across unrelated sessions. Persist corrections as durable
file updates — not just as chat replies.

## Tool Use Guidance

- Run only shell commands from `AGENTS.md` or the relevant package `README`.
- Do not run commands that modify files outside the repository root.
- Validate changes with `pytest -q` in the affected package before proposing a PR.
- Never use the Python heredoc construct in bash — prefer `python -c "..."` instead.

## Validation

Before proposing a merge, run in the affected package directory:

```bash
ruff check .
pytest -q
```

## Feedback Loop

When a correction is needed:

| Type | Where to record |
|---|---|
| Plugin protocol or registry rule | Update `AGENTS.md` |
| Upstream OSS contract | Update `../calibrated_explanations/CONTRIBUTOR_INSTRUCTIONS.md` |
| Platform-specific Gemini quirk | Add a bullet to this file |

## Key Documentation

| Document | Purpose |
|---|---|
| `AGENTS.md` | Plugin protocol, registry rules, release relationship |
| `../calibrated_explanations/CONTRIBUTOR_INSTRUCTIONS.md` | Upstream OSS canonical rules |
| `../calibrated_explanations/docs/improvement/adrs/ADR-006-plugin-model.md` | Plugin trust model |
| `../calibrated_explanations/docs/improvement/adrs/ADR-014-plugin-interface.md` | Plugin interface |
