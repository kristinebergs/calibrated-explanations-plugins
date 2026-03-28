# calibrated-explanations-plugins

Official plugin monorepo for `calibrated-explanations`.

## Upstream docs

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- CE installation guide: <https://calibrated-explanations.readthedocs.io/en/latest/get-started/installation.html>
- CE plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

This repository separates official packages into three plugin families:

- `calibration`
- `explanation`
- `visualization`

It publishes both metapackages and individual plugin packages.

## What counts as "official"

Official plugins are not discovered by scanning all directories. The official
set is defined by dependencies in the family metapackages:

- `calibrated-explanations-calibration`
- `calibrated-explanations-explanation`
- `calibrated-explanations-visualization`

CI runtime checks resolve official plugins from those dependency lists.
The umbrella metapackage (`calibrated-explanations-plugins`) only aggregates
the three family metapackages.

## Install

Install the curated official set:

```bash
pip install calibrated-explanations-plugins
```

Install one family:

```bash
pip install calibrated-explanations-calibration
```

Install one plugin:

```bash
pip install calibrated-explanations-calibration-example
```

## Repository layout

- `packages/calibration/`: calibration plugin distributions
- `packages/explanation/`: explanation plugin distributions
- `packages/visualization/`: visualization plugin distributions
- `packages/meta/`: official metapackages
- `templates/plugin/`: package scaffold guidance
- `scripts/`: validation, scaffolding, and CI helper scripts
- `docs/`: user-facing install and package guidance

## Maintainer workflow

Create new packages through the scaffold:

```bash
python scripts/scaffold_package.py --help
```

Validate the repo structure locally:

```bash
python scripts/validate_repo_structure.py
```

Package releases stay tag-driven and independent. Push a tag in the form
`pkg/<distribution-name>/v<version>` to publish exactly one package, then use
`docs/maintainer-release.md` for bootstrap order and release notes.

To attach a new plugin as an official package:

1. Scaffold the package under the right family directory.
2. Add the plugin distribution to that family metapackage dependencies.
3. Run `python scripts/check_meta_package_sync.py` and
   `python scripts/list_official_plugin_packages.py` to verify inclusion.
