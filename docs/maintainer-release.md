# Maintainer release notes

## Release model

Each package in this repository is versioned independently.

The `Release PyPI Packages` workflow publishes exactly one package, resolved from
the pushed package-specific tag.

Official plugin coverage is dependency-driven:

- family metapackages define which plugin distributions are official
- runtime CI resolves official plugins from those dependency lists
- directory presence alone does not make a package official

## Package tag format

Use this tag format for package releases:

```text
pkg/<distribution-name>/v<version>
```

Examples:

- `pkg/calibrated-explanations-calibration-example/v0.1.0`
- `pkg/calibrated-explanations-calibration/v0.1.0`

## Typical workflow

1. Bump `project.version` in the changed package.
2. If this is a new official plugin, add it to the matching family metapackage dependencies.
3. Run `python scripts/check_meta_package_sync.py`.
4. Merge the change to the default branch.
5. Create the package tag using the package-specific format.
6. Push the tag; the release workflow starts automatically.

## Bootstrap order

For the first repository release, tag and publish packages in this order:

1. Individual plugin packages
2. Family metapackages
3. The umbrella `calibrated-explanations-plugins` metapackage

Family and umbrella metapackages only need a new release when dependency
membership or `calibrated-explanations` compatibility ranges change.
