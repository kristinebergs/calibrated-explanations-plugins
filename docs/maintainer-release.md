# Maintainer release notes

Each package is versioned independently and released from a package-specific
tag:

```text
pkg/<distribution-name>/v<version>
```

Example: `pkg/calibrated-explanations-visualization-plotly/v0.3.0`.

A tag alone never publishes anything: the release workflow gates every tag
with `python scripts/lifecycle.py release`, which rejects non-mature plugins,
invalid or empty metapackage curation, tag/version mismatches, and commits not
reachable from `main`. Publication happens through PyPI trusted publishing in
the protected `pypi` GitHub environment — that approval is the final gate.

## Releasing a package

1. Confirm the policy is clean: `python scripts/lifecycle.py check`.
2. Bump `project.version` in the package's `pyproject.toml`.
3. Regenerate the index: `python scripts/lifecycle.py index` and commit.
4. Merge to `main` through a reviewed PR.
5. Dry-run the gate locally:

   ```bash
   python scripts/lifecycle.py release --tag pkg/<name>/v<version> --default-branch origin/main
   ```

6. Tag the **merged** commit and push the tag; the workflow re-verifies
   everything, builds, validates the artifact, and publishes after `pypi`
   environment approval.

## First publication of a new distribution

Create a PyPI *pending publisher* for this repository and the
`release-pypi.yml` workflow before pushing the first tag, so the project is
owned by the CE maintainer account from the first upload.

## Bootstrap order

1. Individual mature plugins.
2. Family metapackages (only possible once non-empty).
3. The umbrella `calibrated-explanations-plugins` (only once every family
   metapackage is non-empty and released).

Deprecated packages have no release path; an exceptional security or
migration release would be a separately reviewed, temporary workflow change.
