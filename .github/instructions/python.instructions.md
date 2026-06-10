---
applyTo: "packages/**/*.py"
---

# Python Conventions — calibrated-explanations-plugins

These instructions apply to all Python source files under `packages/`.
See `AGENTS.md` for the full plugin protocol and ADR links.

## Protocol Extension

Plugins extend Protocol classes — never subclass base implementations:

```python
from calibrated_explanations.protocols import <FamilyProtocol>

class MyPlugin:
    """Plugin: <description>. Implements <FamilyProtocol>."""
    ...
```

Do NOT import from or subclass `CalibrationExplainer`, `WrapCalibratedExplainer`,
or any base class in the CE library. Implement the Protocol interface only.

## Type Hints

- Required on all public function signatures.
- Use `from __future__ import annotations` for forward references.
- Use `from typing import Any, Optional, Protocol` as needed.

## Docstrings

- **Google-style** — one-line summary, then `Args:`, `Returns:`, `Raises:`.
- Required on all public functions, classes, and methods.

## Imports

- Wrap optional (heavy) dependencies in `try/except ImportError` — lazy import pattern
  (ADR-015). If the dependency is unavailable, omit the plugin from its registry `visible`
  set; do not raise at import time.
- Use relative imports within a package.
- Expose public API through `__all__` in `__init__.py`.
- Add `__path__ = __import__('pkgutil').extend_path(__path__, __name__)` to every
  package `__init__.py`.

## Registry

Register every plugin in the family registry — not in CE's internal registry:

```python
# packages/<family>/<name>/registry.py
from <family>.registry import register

register(
    name="<plugin-name>",
    factory=MyPlugin,
    visible={"<optional-dep>"},  # empty set if always visible
)
```

## Linting

- `ruff` with `target-version = "py310"` (minimum supported).
- Run `ruff check .` before committing.
- Never use `print()` in production code — use `logging`.

## CE Version Compatibility

Check `CalibrationExplainer._API_VERSION` compatibility in your plugin's `__init__.py`
or registry entry. Explicitly document which CE versions your plugin supports.

## Naming

- Uppercase `X`, `y` for feature arrays / target arrays (sklearn convention).
- Lowercase `x`, `y` for single instances only.
