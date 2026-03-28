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
- README install and compatibility text

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
