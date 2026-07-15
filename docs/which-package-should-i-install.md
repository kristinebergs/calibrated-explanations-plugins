# Which package should I install?

Choose based on what you need and on each package's lifecycle status. The
authoritative per-package listing is the generated
[package-index.md](package-index.md); lifecycle definitions are in
[plugin-lifecycle.md](plugin-lifecycle.md).

Upstream CE docs:

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- CE installation guide: <https://calibrated-explanations.readthedocs.io/en/latest/get-started/installation.html>
- CE plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

## The curated default set (from PyPI, once released)

The metapackages install only plugins that completed a maturity review and
were explicitly curated:

```bash
pip install calibrated-explanations-plugins
```

Or one family:

```bash
pip install calibrated-explanations-calibration
pip install calibrated-explanations-explanation
pip install calibrated-explanations-visualization
```

> **Note**: no plugin has completed a maturity review yet, so the curated sets
> are currently empty and the metapackages have not been published.

## Individual mature plugins (from PyPI)

Mature plugins are installable individually with `pip install
<distribution-name>`. There are currently none; see the "Mature" sections of
[package-index.md](package-index.md) as promotions land.

## Experimental plugins (from source only)

Experimental plugins are **not published to PyPI**. Install them from a
repository checkout for development or evaluation:

```bash
git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
cd calibrated-explanations-plugins
pip install ./packages/<family>/<distribution-name>
```

Current experimental plugins:

- `calibrated-explanations-calibration-example` — example calibration wiring
- `calibrated-explanations-calibration-idr` — IDR regression interval
  calibration (requires Python `>=3.13` and a source-installed `isodistrreg`
  backend; see its README)
- `calibrated-explanations-explanation-factual-example` — example factual
  explanation wiring
- `calibrated-explanations-explanation-alternative-example` — example
  alternative explanation wiring
- `calibrated-explanations-explanation-factual-lime` — factual LIME
  explanations
- `calibrated-explanations-explanation-factual-shap` — factual SHAP
  explanations
- `calibrated-explanations-visualization-example` — example visualization
  wiring
- `calibrated-explanations-visualization-plotly` — Plotly visualization
  layouts
- `calibrated-explanations-visualization-dashboard` — dashboard visualization
- `calibrated-explanations-visualization-factual-shap` — SHAP visualization

Each experimental README documents its limitations and exact source-install
steps.

## Naming model

Individual plugin packages use this form:

- `calibrated-explanations-calibration-<slug>`
- `calibrated-explanations-explanation-<slug>`
- `calibrated-explanations-visualization-<slug>`

Metapackages use these names:

- `calibrated-explanations-plugins`
- `calibrated-explanations-calibration`
- `calibrated-explanations-explanation`
- `calibrated-explanations-visualization`

If you are authoring or reviewing a plugin package rather than installing one,
start with the upstream plugin contract and
[plugin-lifecycle.md](plugin-lifecycle.md). A plugin becomes part of a curated
metapackage only after it is mature **and** a separate curation decision adds
it to the family metapackage dependencies.
