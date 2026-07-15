# Plugin lifecycle, maturity, curation, and publication

This document defines the lifecycle and governance model for every package in
this repository. The authoritative machine-readable state lives in each
package's `pyproject.toml`:

```toml
[tool.ce_plugin_repo]
family = "<calibration|explanation|visualization>"
status = "<experimental|mature|deprecated>"
import_name = "<python import package>"
```

There is no other persisted lifecycle flag: PyPI eligibility is derived from
`status`, and curation is derived from family metapackage dependencies.
Metapackages declare `family = "meta"` and **no** status.

Runtime trust (`plugin_meta["trusted"]`, `CE_TRUST_PLUGIN`), scientific
validity, lifecycle status, PyPI eligibility, and metapackage curation are
five different concepts. None implies another.

## Status definitions

### `experimental`

A plugin being developed or evaluated. It:

- is permitted in the repository and must satisfy the repository structure and
  plugin contract (`scripts/validate_repo_structure.py`);
- must have tests appropriate to its current implementation;
- may be installed from source for development
  (`pip install ./packages/<family>/<name>`);
- is **never** published through the official PyPI workflow
  (`scripts/resolve_release_tag.py` rejects it);
- **never** appears in a family metapackage
  (`scripts/check_meta_package_sync.py` rejects it);
- must not be described as official, stable, recommended, or available from
  PyPI;
- must declare `Status: \`experimental\``, an experimental warning, and known
  limitations in its README.

### `mature`

A plugin that has completed the maturity review (below). It:

- is eligible for individual PyPI publication via the release workflow;
- passes release-grade package, artifact, compatibility, and runtime checks
  (wheel-based validation in CI);
- has a named maintainer in `project.maintainers` and licence metadata;
- documents supported CE and Python versions, assumptions, limitations, and
  failure modes;
- **may** be considered for a family metapackage, but is not automatically
  included — curation is a separate decision.

### `deprecated`

A plugin that is no longer recommended. It:

- never appears in a family metapackage;
- must carry a prominent `**Deprecated**` notice and identify its replacement
  or migration path when one exists (or state that none exists);
- remains discoverable in `docs/package-index.md`;
- does not receive ordinary releases; the tag-push release path rejects it;
- may receive an exceptional security or migration release only through the
  maintainer-approved `workflow_dispatch` override on the release workflow
  (see "Deprecation and emergency handling");
- returns to `mature` only through a new maturity review — never silently.

There is **no persisted `candidate` status**. A plugin under maturity review
remains `experimental` until the promotion PR merges; `candidate` may be used
as a label or review concept only.

## Official versus community plugins

- **Community plugin** — externally owned and published. It may be listed for
  discoverability, but it is not released, maintained, or guaranteed by the CE
  plugin maintainers. Listing is not a security, scientific, or maintenance
  endorsement.
- **Experimental repository plugin** — incubated in this repository; not
  publishable.
- **Mature official plugin** — accepted for official publication and
  maintenance (`status = "mature"`).
- **Curated plugin** — a mature official plugin additionally selected into a
  family metapackage (recommended default installation).
- **Deprecated official plugin** — formerly mature; no longer recommended.

"Official", "mature", "trusted", and "curated" are not interchangeable. An
external plugin may remain an independently published community plugin
indefinitely without becoming official.

## Curation model

Family metapackage dependency lists are the authoritative curated plugin sets.
Invariants enforced by `scripts/check_meta_package_sync.py` (shared logic in
`scripts/repo_packages.py`) and covered by tests:

1. A family metapackage depends only on plugins whose status is `mature`.
2. A family metapackage depends only on plugins of its own family.
3. Experimental and deprecated plugins never appear in a metapackage.
4. A mature plugin does not have to appear in a metapackage.
5. The umbrella metapackage (`calibrated-explanations-plugins`) depends on
   exactly the three family metapackages.
6. Metapackage inclusion means "recommended default installation", not merely
   "available on PyPI".
7. Example or demonstration packages are not included merely to keep a
   metapackage non-empty; an empty family metapackage is valid.
8. A curated plugin must not contradict the metapackage's advertised
   `requires-python` range. This is checked automatically by sampling CPython
   minor versions 3.8–3.14 with the `packaging` library; unusual specifiers
   beyond that sampling remain a manual review item.

Curation decisions must additionally weigh dependency weight, platform
restrictions, Python compatibility, CE compatibility, maintenance risk, and
general usefulness. These are review judgements and are documented in the
curation PR, not automated.

## Maturity review

### Mandatory general gates

A plugin may be promoted to `mature` only when all of the following hold:

1. Valid package metadata (name, version, description, readme, dependencies).
2. A licence compatible with publication and redistribution, declared in
   `project.license` (or `license-files`).
3. Declared direct runtime dependencies.
4. A named maintainer in `project.maintainers`.
5. A clear support and issue-reporting route documented in the README.
6. Documented supported Python and calibrated-explanations versions.
7. Tests executed from a built wheel
   (`python scripts/runtime_check_package.py --package-path <pkg>`).
8. No dependency on undocumented private CE members.
9. Deterministic and safe entry-point registration; no network access, file
   modification, package installation, or other surprising side effects at
   import time.
10. Documented configuration (including `plugin_meta["config_schema"]` where
    runtime config is consumed).
11. Documented assumptions, limitations, and failure modes.
12. No known critical security vulnerabilities in direct dependencies.
13. An available or project-controlled PyPI distribution name, and a clear
    decision about who owns and maintains the PyPI project.
14. Passing repository policy and release checks
    (`validate_repo_structure.py`, `check_meta_package_sync.py`,
    `resolve_release_tag.py` dry run).

### Family-specific technical gates

**Calibration plugins** must document and test: the calibration or interval
property they claim; the assumptions under which it is expected to hold;
supported prediction modes and tasks; numerical shape and boundary behaviour;
reproducibility where randomness is involved; and at least one test tied to a
canonical or independently checkable expected result.

**Explanation plugins** must document and test: the exact semantics of the
explanation output; supported factual/alternative modes; supported prediction
tasks; preservation of uncertainty semantics; behaviour for unsupported inputs
and modes; and at least one independently checkable semantic example.

**Visualization plugins** must document and test: the meaning of each visual
encoding; the correspondence between rendered elements and the underlying
PlotSpec or explanation payload; headless rendering; behaviour for missing,
extreme, and interval-valued inputs; and the absence of transformations that
misrepresent signs, magnitudes, intervals, or classes.

**Research-derived plugins** must cite the underlying method and clearly
distinguish: properties established by the original method; properties
established by the CE integration; assumptions not tested by ordinary software
tests; and known deviations from the reference implementation.

Mature status asserts that the plugin passed this review. It does **not**
assert universal scientific validity.

## Promotion workflow

For a plugin already in this repository, the normal readiness signal is a
dedicated **maturity-promotion pull request** using
`.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`. The PR must:

1. change `status = "experimental"` to `status = "mature"` in
   `pyproject.toml`;
2. resolve all mandatory maturity criteria (maintainers, licence, README
   with `Status: \`mature\`` and a `pip install <name>` command, evidence);
3. update lifecycle documentation
   (`python scripts/generate_package_index.py`);
4. pass the full mature-package validation suite — CI detects the status
   transition (`scripts/list_promotion_candidates.py`) and runs release-grade
   wheel validation for the promoted package regardless of changed-package
   optimisations;
5. link the prior review issue (public intake issue where applicable);
6. receive explicit approval from the responsible code owner (enforced by
   `.github/CODEOWNERS` on `pyproject.toml` changes).

Metapackage inclusion is normally a **separate** decision (separate PR or at
least a separate commit). Promoted plugins are never added to a metapackage
automatically.

Workflow labels (aids only, never authoritative metadata): `maturity-review`,
`publication-request`, `metapackage-review`, `deprecated`, and optionally
`candidate` for plugins under review.

## Public external-contributor route

This repository is private, so the public entry point is the public
`kristinebergs/calibrated_explanations` repository: the
**"Plugin publication and maturity request"** issue form
(`.github/ISSUE_TEMPLATE/plugin_publication_request.yml` there; staged copy and
installation notes in `docs/public-intake/`). The form supports:

1. review of an externally hosted plugin for possible adoption into this
   monorepo (accepted work is transferred here after maintainer triage and
   starts as `experimental`);
2. promotion of an existing experimental monorepo plugin by a contributor who
   already has access;
3. community-plugin listing for discoverability only.

The form does not allow a contributor to self-authorise publication. Final
maturity and publication authority remains with the designated CE plugin
maintainers.

Abandoned external contributions (no contributor response for 90 days during
review) are closed; the work may be adopted by a maintainer willing to become
the named maintainer, or dropped. Ownership transfer of a PyPI name to project
control must be agreed before first official publication.

## Release process (maintainers)

See `docs/maintainer-release.md` for tag format and ordering. Enforcement
summary — a correctly formatted tag alone never publishes anything:

- `scripts/resolve_release_tag.py` rejects: experimental plugins; deprecated
  plugins (without the override); metapackages whose dependencies are unknown,
  from the wrong family, experimental, or deprecated; tags whose version does
  not match `project.version`; and commits not reachable from the protected
  default branch (`--default-branch origin/main`).
- The workflow builds the artifact, revalidates it from the wheel, and
  publishes via PyPI **trusted publishing** from the protected `pypi` GitHub
  environment. No API tokens are stored in the repository.
- First publication of a new distribution is bootstrapped by a maintainer
  creating a PyPI "pending publisher" for this repository and workflow, so the
  project is owned by the CE maintainer account from the first upload.
- Release approvers are the reviewers required by the `pypi` environment
  protection rules and `.github/CODEOWNERS`.
- Release provenance: trusted publishing generates PEP 740 attestations where
  supported; keep it enabled.

## Deprecation and emergency handling

- **Who may deprecate:** the code owners of `packages/meta/` and the affected
  package (see `.github/CODEOWNERS`). Deprecation is a PR changing
  `status = "deprecated"` plus the required README notice.
- **Required notice:** a prominent `**Deprecated**` section naming the
  replacement or migration path when one exists, or stating that none exists
  (enforced by `validate_repo_structure.py`).
- **Metapackage removal:** the same PR must remove the plugin from any family
  metapackage; CI fails otherwise.
- **Old releases:** existing PyPI releases remain available by default.
  Releases are **yanked** when they are actively harmful: critical security
  vulnerabilities, data-corrupting bugs, or scientifically misleading output.
- **Critical vulnerabilities:** see `SECURITY.md`. Fix and release (if
  mature), or deprecate and yank affected releases.
- **Exceptional deprecated-package release:** security or migration releases
  only, via the release workflow's `workflow_dispatch` input
  `allow-deprecated: true`, which still runs inside the protected `pypi`
  environment and therefore requires maintainer approval. The ordinary
  tag-push path never allows it.
- **Return to mature:** requires a new maturity-promotion PR with a full
  review; never silent.

## Installing plugins

- **Curated set (mature plugins only), from PyPI once released:**
  `pip install calibrated-explanations-plugins` (or a family metapackage).
- **Individual mature plugin, from PyPI:** `pip install <distribution-name>`.
- **Experimental plugin, from source only:**

  ```bash
  git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
  pip install ./calibrated-explanations-plugins/packages/<family>/<distribution-name>
  ```

  Experimental plugins are not on PyPI; any document claiming otherwise is a
  policy violation caught by `scripts/check_docs_install_commands.py`.

The generated `docs/package-index.md` lists every package by lifecycle bucket
(metapackages, mature curated, mature standalone, experimental, deprecated) and
is kept honest by `python scripts/generate_package_index.py --check` in CI.
