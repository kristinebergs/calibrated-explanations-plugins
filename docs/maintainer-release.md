# Maintainer release notes

## Release model

Each package in this repository is versioned independently.

The `Release PyPI Packages` workflow publishes exactly one package, resolved
from the pushed package-specific tag. **A tag alone never publishes anything**:
`scripts/resolve_release_tag.py` gates every release on lifecycle policy
before the build starts.

Release eligibility:

- **plugins** — only `status = "mature"`; experimental plugins are rejected,
  deprecated plugins are rejected on the tag-push path;
- **metapackages** — rejected while any curation invariant fails (unknown,
  wrong-family, experimental, or deprecated dependency; stale umbrella;
  requires-python conflicts);
- **every release** — the tag version must equal `project.version`, and the
  tagged commit must be reachable from `origin/main` (no releases from
  unmerged or unreviewed commits).

Publication uses PyPI **trusted publishing** from the protected `pypi` GitHub
environment. First publication of a new distribution is bootstrapped by
creating a PyPI *pending publisher* for this repository/workflow so the
project is under CE maintainer control from the first upload. See
`docs/plugin-lifecycle.md` for ownership and approval authority.

## Package tag format

```text
pkg/<distribution-name>/v<version>
```

Examples:

- `pkg/calibrated-explanations-visualization-plotly/v0.3.0`
- `pkg/calibrated-explanations-calibration/v0.2.0`

## Typical workflow

1. Confirm the package is `mature` (plugins) or curation-clean (metapackages):
   `python scripts/check_meta_package_sync.py`.
2. Bump `project.version` in the changed package.
3. Regenerate the index: `python scripts/generate_package_index.py`.
4. Merge the change to the default branch through review.
5. Create the package tag **on the merged commit** and push it; the release
   workflow starts automatically and re-verifies everything.

Dry-run the gate locally before tagging:

```bash
python scripts/resolve_release_tag.py --tag pkg/<name>/v<version> --default-branch origin/main
```

## Exceptional deprecated-package release

Deprecated packages receive no ordinary releases. For a security or migration
release only, a maintainer runs the release workflow manually
(`workflow_dispatch`) with the existing tag and `allow-deprecated: true`. The
run still executes inside the protected `pypi` environment, so it requires
environment approval. Document the justification in the deprecation issue.

## Bootstrap order

For the first repository release, tag and publish packages in this order:

1. Individual mature plugin packages
2. Family metapackages
3. The umbrella `calibrated-explanations-plugins` metapackage

Family and umbrella metapackages only need a new release when curated
membership or `calibrated-explanations` compatibility ranges change.
