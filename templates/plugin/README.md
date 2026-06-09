# Plugin template

Create new official packages through:

```bash
python scripts/scaffold_package.py --help
```

Reference docs:

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- CE installation guide: <https://calibrated-explanations.readthedocs.io/en/latest/get-started/installation.html>
- CE plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

Family-specific scaffold targets:

- `calibration`: interval calibrator packages implement `IntervalCalibratorPlugin` and expose `create(...)` through `calibrated_explanations.plugins`
- `explanation`: explanation packages implement `ExplanationPlugin` and expose `supports`, `supports_mode`, `initialize`, and `explain_batch`
- `visualization`: visualization packages ship both a plot builder and a plot renderer through the PlotSpec entry-point groups

The scaffold enforces:

- family placement
- public package naming
- import package naming
- family-appropriate entry-point registration
- family-appropriate `plugin_meta` structure
- optional provisional `plugin_meta["config_schema"]` for plugins that receive
  runtime config through CE context objects
- README install and compatibility text

## Provisional plugin config

Official plugins may include a provisional `plugin_meta["config_schema"]` while
OSS CE, CEE, and this plugin repo harden config behavior together. This schema is
for integration validation only; it is not yet a compatibility-frozen public
plugin config standard.

Use this shape only when the plugin actually consumes runtime config:

```python
plugin_meta = {
    "config_schema": {
        "version": 1,
        "additional_properties": False,
        "keys": {
            "label_prefix": {"type": "str", "default": "example"},
            "enabled_labels": {"type": "list[str]", "default": []},
            "diagnostic_token": {"type": "str", "required": False, "sensitive": True},
        },
    },
}
```

## Attaching a plugin to the official runtime suite

A package becomes "official" only when it is listed in the matching family
metapackage dependencies:

- calibration plugin -> `packages/meta/calibrated-explanations-calibration/pyproject.toml`
- explanation plugin -> `packages/meta/calibrated-explanations-explanation/pyproject.toml`
- visualization plugin -> `packages/meta/calibrated-explanations-visualization/pyproject.toml`

After adding the dependency, verify:

```bash
python scripts/check_meta_package_sync.py
python scripts/list_official_plugin_packages.py
```

If the plugin path appears in `list_official_plugin_packages.py` output, CI will
run the all-plugin artifact runtime check for it.
