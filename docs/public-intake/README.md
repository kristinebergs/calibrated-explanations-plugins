# Public contribution intake — staging

This plugin repository is **private**, so an issue template here cannot serve
as the external-contribution route. The public entry point is the public
`kristinebergs/calibrated_explanations` repository.

## What has been installed where

The following changes have been placed in the local working tree of the public
repository (`../calibrated_explanations`) and must be reviewed and committed
there by a maintainer:

1. `plugin_publication_request.yml` (staged copy in this directory) installed
   as:

   ```text
   calibrated_explanations/.github/ISSUE_TEMPLATE/plugin_publication_request.yml
   ```

2. A "Plugin publication and maturity requests" section appended to:

   ```text
   calibrated_explanations/CONTRIBUTING.md
   ```

   It links to the issue form and states that publication authority remains
   with the CE plugin maintainers.

If those working-tree changes are lost, reinstall the form by copying the
staged `plugin_publication_request.yml` from this directory to the path above.

## The two supported request cases

1. **External plugin adoption** — a contributor's externally hosted plugin is
   reviewed for possible adoption into this monorepo. After maintainer triage,
   accepted work is transferred here and starts as `experimental`.
2. **Maturity promotion** — a contributor with repository access asks for an
   experimental monorepo plugin to be promoted; triage results in a
   maturity-promotion PR here (see
   `.github/PULL_REQUEST_TEMPLATE/maturity_promotion.md`).

A third lightweight case — community-plugin listing for discoverability — is
also offered by the form; it never implies endorsement or publication.

Contributors cannot self-authorise publication through the form. Final
maturity, publication, and curation authority rests with the designated CE
plugin maintainers (see `.github/CODEOWNERS`).
