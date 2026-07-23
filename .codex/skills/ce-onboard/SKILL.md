---
name: ce-onboard
description: >
  Read-only session primer for CE-first invariants, key files, and skill routing at session start.
---

## Inputs

- **`content`** (text, required): The input relevant to this skill. See instructions for details.

## Output Format

Format: `markdown`

Required sections:
- output

# Ce Onboard — Core Instructions

# CE Onboard

## Arguments
- `--baseline` — run environment checks (see section 6) before coding

---

## 1. Project identity

`calibrated_explanations` is a scikit-learn-compatible Python XAI library.
It extracts calibrated factual rules, alternative rules, and prediction
intervals from any model.

- **Core entry points**: `CalibratedExplainer`, `WrapCalibratedExplainer`
- **Canonical rules**: `CONTRIBUTOR_INSTRUCTIONS.md`
- **Public install**: `pip install calibrated-explanations`

---

## 2. The CE-First invariants

1. **Always use `WrapCalibratedExplainer`** — never subclass or bypass it.
2. **Fit → Calibrate → Explain** — that is the only valid lifecycle order.
3. **Never access `_private` members** — if you need it, there is a public accessor or the feature does not exist yet.
4. **Lazy imports** — do not add eager top-level imports for heavy libraries (`matplotlib`, `pandas`, `catboost`…) in `__init__.py`.
5. **Plugin-first** — new functionality belongs in `plugins/`, not `core/`.
6. **ADR wins** — if a plan and an ADR conflict, the ADR takes precedence.
7. **Fallback visibility** — every fallback emits `_LOGGER.info()` AND `warnings.warn(..., UserWarning)`. No silent fallbacks ever.
8. **Numpy docstrings** — all public functions and classes use numpy-style.
9. **Coverage gate** — `pytest --cov=... --cov-fail-under=90` must pass.
10. **Test naming** — `test_should_<behavior>_when_<condition>`.

---

## 3. Key files (read on first touch, not every session)

| File | What it tells you |
|---|---|
| `CONTRIBUTOR_INSTRUCTIONS.md` | Canonical CE-First rules **(authoritative)** |
| `development/current-work/vX.Y.Z_plan.md` | Sole active release plan: included work + outstanding gates |
| GitHub issues/milestones | Proposed work and approved release scope |
| `QUICK_API.md` | Public API surface cheat-sheet |
| `tests/README.md` | Test structure and coverage requirements |

---

## 4. Skill routing (most-used skills)

| Intent | Skill |
|---|---|
| Code review | `ce-code-review` |
| Quality audit | `ce-code-quality-auditor` |
| Write tests | `ce-test-author` |
| Design tests for gaps | `ce-test-creator` |
| Write docstrings | `ce-docstring-author` |
| Write RTD pages | `ce-rtd-writer` |
| Audit RTD | `ce-rtd-auditor` |
| Scaffold a plugin | `ce-plugin-scaffold` |
| Implement a fallback | `ce-fallback-impl` |
| Binary/multiclass explanations | `ce-classification` |
| Regression intervals | `ce-regression-intervals` |
| Factual explanations | `ce-factual-explain` |
| Alternative explanations | `ce-alternatives-explore` |
| Check release gate | `ce-release-check` |
| Implement a release task | `ce-release-task` |
| Plan a release | `ce-release-planner` |
| Consult ADRs | `ce-adr-consult` |
| Create or update a skill | `ce-skill-creator` |

For the full skill list, browse `.claude/skills/` or run `ce-skill-registry-sync`.

---

## 5. Module layout (ADR-001 boundary)

```
src/calibrated_explanations/
├── core/           # CalibratedExplainer, WrapCalibratedExplainer — do NOT modify unless necessary
├── plugins/        # All extensible functionality — registry, calibrators, plotters, explanations
├── calibration/    # Venn-Abers and conformal calibration logic
├── viz/            # PlotSpec IR + matplotlib adapter (ADR-007, ADR-016, ADR-023)
├── utils/          # Shared helpers, deprecation, logging
└── ce_agent_utils.py  # Backward compatibility only — not the agent interface
```

**Rule**: Code in `core/` must not import from `plugins/`. Plugins import from `core/`, never the reverse.

---

## 6. Environment checks (only if `--baseline` was passed)

```bash
python -c "import calibrated_explanations; print(calibrated_explanations.__version__)"
python -m pytest -q --co -q   # list tests without running
make local-checks-pr           # fast gates (lint + type + quick tests)
```

---

## 7. Frequent agent mistakes

- Using `n_top_features=n` → correct param is `filter_top=n` on explain calls.
- Importing from `calibrated_explanations.core.*` directly → use top-level import.
- Adding a new fallback without `warnings.warn(UserWarning)` → always warn.
- Writing tests without `test_should_<behavior>_when_<condition>` naming.
- Adding eager `import matplotlib` at module top level → always import lazily.