---
applyTo:
  - "packages/**/tests/**/*.py"
  - "packages/**/*test*.py"
---

# Test Conventions — calibrated-explanations-plugins

## Structure

- Tests live in `packages/<family>/<name>/tests/`
- File naming: `test_<module>.py`
- Function naming: `should_<behavior>_when_<condition>`
- Pattern: Arrange–Act–Assert with one logical assertion block per test

## What to Test

Every plugin package must have tests covering:
1. **Registry registration** — plugin is discoverable after import
2. **Protocol conformance** — plugin implements all required Protocol methods
3. **Lazy import guard** — if optional dependency is missing, plugin is excluded from
   `visible` set without raising at import time
4. **CE-First lifecycle** — plugin works end-to-end with `WrapCalibratedExplainer`
5. **Fallback behavior** — plugin degrades gracefully when its optional dep is absent

## CE Integration Rules

- **Integration tests MUST use the real `calibrated-explanations` library** — no mocking
  of CE internals. Mock only external non-CE dependencies.
- Use `conftest.py` fixtures to set up shared `WrapCalibratedExplainer` instances.
- Seeded random data only — no real datasets in tests.

## Determinism

- No real network calls, no real clock, no unseeded randomness.
- Use `pytest.MonkeyPatch` / `unittest.mock` for external services.
- Seed: `np.random.seed(42)` or pass `random_state=42` to sklearn utilities.

## Markers

- `@pytest.mark.integration` — tests needing the real CE library (not just unit mocks)
- `@pytest.mark.slow` — tests taking >2 seconds

## Coverage

- Coverage gate: `pytest --cov=packages/<family>/<name> --cov-fail-under=85`
- Do not modify production code to add branches that only exist for tests.

## Parity Tests

If a plugin reimplements or wraps OSS CE behavior, include a parity test:
```python
np.testing.assert_allclose(plugin_result, ce_result, rtol=0, atol=1e-10)
```

## Performance

- Unit tests: < 200ms
- Integration tests: < 5s
