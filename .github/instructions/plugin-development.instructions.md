---
applyTo: "packages/**/*.py"
---

# Plugin Development Guidelines

These instructions apply to all Python source files under `packages/`.
See `AGENTS.md` for the full upstream context and ADR links.

## Protocol Extension Pattern

Every plugin must extend the Protocol class, not the base implementation:

```python
from calibrated_explanations.protocols import <FamilyProtocol>

class MyPlugin:
    """Plugin: <description>. Implements <FamilyProtocol>."""
    ...
```

Do NOT subclass `CalibrationExplainer`, `WrapCalibratedExplainer`, or any base
class from the CE library. Implement the Protocol only.

## Registry Entry

Register in the family registry, not in CE's internal registry:

```python
# In packages/<family>/<name>/registry.py
from calibrated_explanations.plugin_registry import register_plugin

register_plugin(
    family="<family>",
    name="<plugin_name>",
    cls=MyPlugin,
    requires=["<optional_dep>"],
    visible=lambda: _has_optional_dep(),
)
```

## Lazy Import Pattern

Wrap all optional dependencies to avoid `ImportError` at import time:

```python
try:
    import optional_dep
    _HAS_OPTIONAL_DEP = True
except ImportError:
    _HAS_OPTIONAL_DEP = False

def _has_optional_dep() -> bool:
    return _HAS_OPTIONAL_DEP
```

The plugin should gracefully degrade when the optional dep is missing.
The `visible` callable controls whether the plugin appears in the registry.
Never raise at module import time.

## API Version Compatibility

Check CE API version at plugin load time:

```python
from calibrated_explanations import __api_version__

PLUGIN_REQUIRES_API = ">=1.0"  # semver range

def check_compatibility() -> None:
    from packaging.specifiers import SpecifierSet
    if __api_version__ not in SpecifierSet(PLUGIN_REQUIRES_API):
        raise RuntimeError(f"Plugin requires CE API {PLUGIN_REQUIRES_API}, got {__api_version__}")
```

## Tests

- Tests live in `packages/<family>/<name>/tests/`
- Use `pytest` with fixtures from `conftest.py` at the package root
- Every public method needs at least one unit test
- Integration tests (requiring the optional dep) must be marked `@pytest.mark.optional`
  and skipped cleanly when the dep is absent

## CHANGELOG

Every PR that changes a plugin package must update the CHANGELOG:
```
## Unreleased

### Added/Changed/Fixed
- <description> (#PR)
```
