# calibrated-explanations-visualization

Family: `meta`

Purpose: Curated visualization plugin metapackage for the calibrated-explanations ecosystem.

## Install

Base installation — the recommended interactive Plotly visualization plugin:

```bash
pip install calibrated-explanations-visualization
```

This installs `calibrated-explanations-visualization-plotly>=0.3.5,<0.4` (and its own
`plotly` dependency). It does **not** install Dash, and it does not install
or require anything needed only for the plugin's live-dashboard mode.

Live dashboards — adds the Plotly plugin's supported Dash dependency set:

```bash
pip install "calibrated-explanations-visualization[live]"
```

This extra delegates to the Plotly plugin's own `[live]` extra; Dash is never
declared directly by this metapackage. Ordinary interactive Plotly figures
(bars, quadrants, the instance explorer, the standalone-HTML dashboard) do
not need `[live]` — it is required only for the launched, server-backed
dashboard.

## Compatibility

`calibrated-explanations>=1.0.0rc2,<2`, Python `>=3.11`, following the
curated Plotly plugin's own compatibility matrix (see that package's README
and `MATURITY.md` for the exact floor/newest-boundary environments).

## Trust and activation

Installing this metapackage (with or without `[live]`) does not automatically
trust, register, or activate the Plotly plugin, and does not replace CE's
built-in plotting. CE's
[plugin trust model](https://github.com/Moffran/calibrated_explanations/blob/main/development/adrs/ADR-006-plugin-registry-trust-model.md)
requires an explicit decision:

```python
from ce_visualization_plotly.plugin import register_plotly_visualization_components

register_plotly_visualization_components()
```

Registration is explicit and idempotent; importing the package alone has no
registration or CE-patching side effects. CE's built-in (matplotlib-based)
plotting remains available and unchanged whether or not the Plotly plugin is
installed or registered — installing this metapackage only makes the Plotly
styles available to opt into.

## Curation policy

This metapackage installs only plugins that completed a maturity review
**and** were explicitly selected as the recommended default set (see
`docs/plugin-lifecycle.md`). Maturity and curation are independent
decisions: a plugin being `mature` does not automatically add it here, and
future mature visualization plugins are not added automatically either.
Currently curated: `calibrated-explanations-visualization-plotly`.
