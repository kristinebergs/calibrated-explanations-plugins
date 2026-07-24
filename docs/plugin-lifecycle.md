# Plugin lifecycle

This is the authoritative lifecycle policy for the plugin monorepo. The
machine-readable state lives in each plugin's `pyproject.toml`:

```toml
[tool.ce_plugin_repo]
family = "<calibration|explanation|visualization>"
status = "<experimental|mature|deprecated>"
import_name = "<python-import-name>"
```

`status` is the single source of truth for lifecycle state; family
metapackage dependency lists are the single source of truth for curation.
There is no other lifecycle flag. Runtime trust (`plugin_meta["trusted"]`)
is an independent concept and never follows from repository status.

Everything below is enforced by `python scripts/lifecycle.py check` and the
release gate (`lifecycle.py release`) unless marked as human review.

## Statuses

**Experimental** — the default for every new plugin (scaffolding enforces it).
Allowed in the repository as long as it satisfies the plugin contract and
structure checks (`scripts/validate_repo_structure.py`) and has package-local
tests. Installed from source only; never released to PyPI and never in a
metapackage.

**Mature** — maintained and release-ready within its documented scope (this is
not a claim of universal scientific validity). May be released individually to
PyPI and may, but need not, be curated into its family metapackage. Requires:

- a named maintainer in `project.maintainers` and licence metadata;
- declared runtime dependencies and documented Python/CE compatibility;
- a README covering purpose, installation, configuration where applicable,
  limitations, and support;
- tests passing from a built wheel
  (`python scripts/runtime_check_package.py --package-path <pkg>`);
- no known use of undocumented private CE APIs (human review);
- an explicit decision about PyPI name ownership (human review).

**Deprecated** — no longer recommended. Never in a metapackage, receives no
ordinary release, and its README must carry a visible deprecation notice with
migration guidance. There is currently no exceptional deprecated-release path;
if one is ever needed it will be added as a separately reviewed workflow
change. Returning to mature requires a new promotion review.

## Curation (metapackages)

1. A family metapackage may be empty in the repository, but an empty
   metapackage cannot be released.
2. A non-empty family metapackage may contain only mature plugins of its own
   family.
3. A mature plugin may remain standalone; curation is a separate decision.
4. The umbrella (`calibrated-explanations-plugins`) depends on exactly the
   three family metapackages and cannot be released while any of them is
   empty or invalid.
5. Example packages are never added just to fill a metapackage, and empty
   metapackages get no artificial dependencies.

Promotion and curation may land in the same PR when the PR explicitly
identifies and justifies both decisions.

## Promotion

Promotion is a PR that flips `status = "experimental"` to `"mature"` using the
template in `.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`. No separate
issue is required for a plugin already in this repository; link a public
intake issue if one exists.

CI validates every changed package from a built wheel, so the promotion PR is
automatically checked at release grade. The automated gates cover metadata,
wheel build, and tests; the reviewer answers the human questions in the
template (supported CE interfaces only, honest semantics and limitations,
acceptable dependencies, PyPI name control, credible maintainer).

## Public intake (external contributors)

Use the **plugin intake issue form** in the authoritative
[`Moffran/calibrated_explanations`](https://github.com/Moffran/calibrated_explanations/issues/new?template=plugin_publication_request.yml)
repository to propose adoption of an external plugin, promotion of an existing
repository plugin, or a community-plugin listing. Submitting the form never
authorises publication; accepted official plugins start here as experimental.

This repository is public. Direct pull requests are accepted for fixes and
development of plugins already maintained or accepted for incubation here.
Maturity-review details (compatibility matrix, PyPI ownership, curation) are
discussed after maintainers confirm a new plugin is relevant, not at intake.

## Release

Releases are tag-driven and per package:

```text
pkg/<distribution-name>/v<version>
```

The release workflow (`.github/workflows/release-pypi.yml`) has two jobs:
build-and-validate (gates the tag with `lifecycle.py release`, builds only the
tagged package plus its mature curated closure, validates the artifact) and
publish (protected `pypi` environment, PyPI trusted publishing, publishes the
already-validated artifact without executing repository code). The gate
enforces: the distribution exists, the tag matches `project.version`, plugins
are mature, curation is valid, metapackages are non-empty, and the tagged
commit is reachable from `main`. The protected `pypi` environment is the final
human approval boundary.

See `docs/maintainer-release.md` for the exact commands.

## Deprecation

Deprecating a plugin is a PR that sets `status = "deprecated"`, removes the
plugin from any metapackage (CI fails otherwise), and adds a README
deprecation notice naming the migration path (or stating none exists).
Existing PyPI releases stay available unless actively harmful — then they are
yanked (see `SECURITY.md`).
