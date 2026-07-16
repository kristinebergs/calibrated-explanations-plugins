# calibrated-explanations-plugins

Plugin monorepo for
[`calibrated-explanations`](https://calibrated-explanations.readthedocs.io/en/latest/),
organised into three plugin families plus curated metapackages:

- `packages/calibration/`
- `packages/explanation/`
- `packages/visualization/`
- `packages/meta/` — curated metapackages

## Lifecycle in one paragraph

Every plugin declares `status = "experimental" | "mature" | "deprecated"` in
its `pyproject.toml` (`[tool.ce_plugin_repo]`). Experimental plugins install
from source only and are never on PyPI or in a metapackage. Mature plugins
(named maintainer, licence, wheel-tested, reviewed) may be released to PyPI
and may additionally be curated into their family metapackage. Deprecated
plugins receive no releases. The complete policy is
[docs/plugin-lifecycle.md](docs/plugin-lifecycle.md); the generated
[docs/package-index.md](docs/package-index.md) lists every package by bucket.

## Install

```bash
# Curated sets and mature plugins, from PyPI once released:
pip install calibrated-explanations-plugins          # umbrella
pip install <distribution-name>                      # one plugin

# Experimental plugins, from a checkout only:
git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
pip install ./calibrated-explanations-plugins/packages/<family>/<distribution-name>
```

No plugin has completed a maturity review yet, so nothing is currently
published and the curated sets are empty.

## Contributing a plugin

**External contributors:** this repository is private — use the plugin intake
issue form in the public
[`calibrated_explanations`](https://github.com/kristinebergs/calibrated_explanations)
repository. Accepted plugins are transferred here and start experimental.

**Collaborators:** scaffold a new (always experimental) package with
`python scripts/scaffold_package.py --help`, and promote it with a PR using
`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`.

## Maintainer workflow

```bash
python scripts/validate_repo_structure.py   # structure + plugin contract
python scripts/lifecycle.py check           # statuses + curation
python scripts/lifecycle.py index --check   # generated package index
python -m pytest tests -q                   # lifecycle policy tests
```

Releases are tag-driven (`pkg/<distribution-name>/v<version>`) and gated by
`python scripts/lifecycle.py release`; see
[docs/maintainer-release.md](docs/maintainer-release.md).
