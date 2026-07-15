# calibrated-explanations-plugins

Plugin monorepo for `calibrated-explanations`.

## Upstream docs

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- CE installation guide: <https://calibrated-explanations.readthedocs.io/en/latest/get-started/installation.html>
- CE plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

This repository separates packages into three plugin families plus
metapackages:

- `calibration`
- `explanation`
- `visualization`
- `meta` (curated metapackages)

## Plugin lifecycle

Every plugin package declares a lifecycle status in its `pyproject.toml`
(`[tool.ce_plugin_repo] status`):

- **experimental** — under development or evaluation; installable from source
  only; never published to PyPI and never part of a metapackage.
- **mature** — passed the maturity review; eligible for individual PyPI
  publication; may additionally be *curated* into a family metapackage.
- **deprecated** — no longer recommended; excluded from metapackages and
  ordinary releases; documents a migration path.

The full policy — status semantics, maturity review gates, promotion workflow,
curation rules, deprecation, and PyPI governance — is in
[docs/plugin-lifecycle.md](docs/plugin-lifecycle.md). The design rationale is
in [docs/adr/ADR-P001-plugin-lifecycle-and-curation.md](docs/adr/ADR-P001-plugin-lifecycle-and-curation.md).

## What counts as "official" and "curated"

The curated (recommended default) plugin sets are defined by the dependencies
of the family metapackages — never by directory presence:

- `calibrated-explanations-calibration`
- `calibrated-explanations-explanation`
- `calibrated-explanations-visualization`

Only plugins with `status = "mature"` may appear there, and mature plugins are
not added automatically: curation is a separate review decision. The umbrella
metapackage (`calibrated-explanations-plugins`) aggregates exactly the three
family metapackages. All curated sets are currently empty; no plugin has
completed a maturity review yet.

Externally owned plugins can remain independently published **community
plugins**; see the lifecycle document for the ecosystem boundary.

## Install

Mature plugins and metapackages install from PyPI once released:

```bash
pip install calibrated-explanations-plugins        # curated set (umbrella)
pip install calibrated-explanations-calibration    # one family
```

Experimental plugins install from a repository checkout only — they are not
published to PyPI:

```bash
git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
pip install ./calibrated-explanations-plugins/packages/<family>/<distribution-name>
```

See the generated [docs/package-index.md](docs/package-index.md) for every
package by lifecycle bucket, and
[docs/which-package-should-i-install.md](docs/which-package-should-i-install.md)
for guidance.

## Repository layout

- `packages/calibration/`: calibration plugin distributions
- `packages/explanation/`: explanation plugin distributions
- `packages/visualization/`: visualization plugin distributions
- `packages/meta/`: curated metapackages
- `templates/plugin/`: package scaffold guidance
- `scripts/`: validation, scaffolding, and CI helper scripts
- `docs/`: lifecycle policy, install guidance, and the generated package index
- `tests/`: lifecycle and governance policy tests

## Contributing a plugin

External contributors: this repository is private. Use the public
**"Plugin publication and maturity request"** issue form in the public
[`calibrated_explanations`](https://github.com/kristinebergs/calibrated_explanations)
repository (see `docs/public-intake/`). Accepted work is transferred here and
starts as `experimental`.

Collaborators: scaffold new packages (always experimental) with:

```bash
python scripts/scaffold_package.py --help
```

Promotion to `mature` happens through a maturity-promotion PR using
`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`.

## Maintainer workflow

Validate the repository locally:

```bash
python scripts/validate_repo_structure.py
python scripts/check_meta_package_sync.py
python scripts/generate_package_index.py --check
python -m pytest tests -q
```

Package releases stay tag-driven and independent
(`pkg/<distribution-name>/v<version>`), but a tag alone never publishes:
`scripts/resolve_release_tag.py` rejects experimental and deprecated packages,
curation violations, version mismatches, and commits not reachable from
`main`. See [docs/maintainer-release.md](docs/maintainer-release.md).
