---
mode: ask
description: "Scaffold a new plugin package: Protocol extension, registry entry, tests, CHANGELOG"
---

Scaffold a new official plugin for `calibrated-explanations-plugins`.

## Inputs Needed

Ask the user for:

1. **Plugin name** — snake_case, e.g. `isotonic_calibration`
2. **Family** — `calibration`, `explanation`, or `visualization`
3. **Description** — one sentence: what this plugin does
4. **Protocol** — which Protocol class it implements (auto-suggest based on family)
5. **Optional dependency** — any pip package this plugin wraps (or "none")
6. **CE API version requirement** — minimum CE API version needed (default: current)

---

## Scaffold Output

Create the following directory and files. Use the templates in `templates/` as the canonical starting point.

### Directory: `packages/<family>/<plugin_name>/`

**`pyproject.toml`**
```toml
[project]
name = "calibrated-explanations-<plugin_name>"
version = "0.1.0"
description = "<description>"
dependencies = [
    "calibrated-explanations>=<ce_version>",
    # "<optional_dep>; extra == 'full'"  # uncomment if optional dep exists
]

[project.optional-dependencies]
full = ["<optional_dep>"]  # if applicable
```

**`<plugin_name>/__init__.py`**
```python
from .<plugin_name> import <PluginClass>

__all__ = ["<PluginClass>"]
```

**`<plugin_name>/<plugin_name>.py`**
- Protocol extension (not subclass)
- Lazy import of optional dep
- `_has_optional_dep()` helper

**`<plugin_name>/registry.py`**
- `register_plugin(family=..., name=..., cls=..., requires=..., visible=...)`
- Called at import time

**`tests/test_<plugin_name>.py`**
- Unit tests for all public methods
- Integration tests marked `@pytest.mark.optional` (skipped if dep absent)
- Fixture: minimal CE explainer compatible with this plugin's Protocol

**`CHANGELOG.md`**
```
# Changelog

## [0.1.0] - Unreleased

### Added
- Initial scaffold for <plugin_name>
```

---

## After Scaffolding

Remind the user that new plugins start with `status = "experimental"`
(source-install only, never on PyPI, never in a metapackage), and to:
1. Run `pytest packages/<family>/<plugin_name>/tests/` to verify the scaffold
2. Run `python scripts/validate_repo_structure.py` to confirm policy compliance
3. Open a PR with the `plugin:new` label
4. Later, promote via a maturity-promotion PR
   (`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`); metapackage
   curation is a separate decision after maturity (see
   `docs/plugin-lifecycle.md`)

> Coordinate major API additions with `@release-coordinator` in the enterprise repo.
