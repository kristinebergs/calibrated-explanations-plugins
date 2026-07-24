# calibrated-explanations-plugins

Official public companion repository for optional
[`calibrated-explanations`](https://github.com/Moffran/calibrated_explanations)
extensions. Packages are independently versioned and organised into
calibration, explanation, and visualization families plus curated
metapackages.

The generated [package index](docs/package-index.md) is authoritative for the
complete inventory, versions, lifecycle state, and curation. Currently, the
visualization family contains the mature Plotly plugin; the calibration and
explanation families have no curated plugins.

## Recommended installation

Install the populated visualization family:

```bash
pip install calibrated-explanations-visualization
```

This installs the mature Plotly visualization plugin. Install the individual
distribution when you intentionally want to manage that package directly or
use its package-specific extras:

```bash
pip install calibrated-explanations-visualization-plotly
```

The umbrella `calibrated-explanations-plugins` package is not the default
recommendation while only one family is populated.

## Lifecycle

- **Experimental:** source-only incubation; not published or curated.
- **Mature:** release-ready within its documented scope; may be published and
  separately selected for a family metapackage.
- **Deprecated:** no longer recommended and removed from curation.

See the [lifecycle policy](docs/plugin-lifecycle.md), generated
[package index](docs/package-index.md), Plotly
[maturity record](packages/visualization/calibrated-explanations-visualization-plotly/MATURITY.md),
and [maintainer release guide](docs/maintainer-release.md).

## Contributing

Propose a new official plugin, promotion, or community listing through the
[authoritative Moffran plugin-intake form](https://github.com/Moffran/calibrated_explanations/issues/new?template=plugin_publication_request.yml).
Accepted official plugins enter this repository as experimental.

Because this repository is public, direct pull requests are accepted for
changes to plugins already under review or maintained here. Use
`python scripts/scaffold_package.py --help` for accepted new packages and the
[maturity-promotion template](.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md)
for promotion. Automated gates and maintainer review determine maturity;
tag validation and the protected PyPI environment govern publication.

## Maintainer checks

```bash
python scripts/validate_repo_structure.py
python scripts/lifecycle.py check
python scripts/lifecycle.py index --check
python -m pytest tests -q
```
