# calibrated-explanations-plugins

Family: `meta`

Purpose: Umbrella metapackage aggregating the curated plugin families for the calibrated-explanations ecosystem.

Install:

```bash
pip install calibrated-explanations-plugins
```

Effective compatibility of the current dependency closure:
`calibrated-explanations>=1.0.0rc2,<2`, Python `>=3.11`. The curated Plotly
plugin determines this CE floor; the umbrella's direct family dependencies
must not be interpreted as broader compatibility.

## Dependency closure

This package depends on exactly the three family metapackages:
`calibrated-explanations-calibration`, `calibrated-explanations-explanation`,
and `calibrated-explanations-visualization`. Curation happens inside each
family metapackage, not here — this package never lists an individual plugin
directly.

As of `0.3.0`, the visualization dependency is pinned to
`calibrated-explanations-visualization>=0.3,<0.4`, which curates the
`calibrated-explanations-visualization-plotly` plugin (see that family's
README). A fresh install of `calibrated-explanations-plugins` therefore now
also installs the Plotly visualization plugin and its own `plotly`
dependency — but not Dash, and not any live-dashboard dependency. This
package does not offer a `[live]` extra; install
`calibrated-explanations-visualization[live]` directly if live dashboards are
needed. Older published `calibrated-explanations-plugins` releases (which
depended on a broader `calibrated-explanations-visualization>=0.1,<1` range)
will resolve to this new visualization-family release on a fresh install
once it is published — their already-published dependency metadata itself
cannot be changed retroactively.

Installing this package does not automatically trust, register, or activate
any curated plugin; each plugin's own README documents the explicit,
supported CE trust/registration APIs.
