# Which package should I install?

Choose the package based on what you need to install.

Upstream CE docs:

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- CE installation guide: <https://calibrated-explanations.readthedocs.io/en/latest/get-started/installation.html>
- CE plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

## Install the standard official set

```bash
pip install calibrated-explanations-plugins
```

## Install one family

Calibration plugins:

```bash
pip install calibrated-explanations-calibration
```

Explanation plugins:

```bash
pip install calibrated-explanations-explanation
```

Visualization plugins:

```bash
pip install calibrated-explanations-visualization
```

## Install one plugin

Example calibration plugin:

```bash
pip install calibrated-explanations-calibration-example
```

Example factual explanation plugin:

```bash
pip install calibrated-explanations-explanation-factual-example
```

Example alternative explanation plugin:

```bash
pip install calibrated-explanations-explanation-alternative-example
```

Example visualization plugin:

```bash
pip install calibrated-explanations-visualization-example
```

## Official naming model

Official individual plugin packages use this form:

- `calibrated-explanations-calibration-<slug>`
- `calibrated-explanations-explanation-<slug>`
- `calibrated-explanations-visualization-<slug>`

Official metapackages use these names:

- `calibrated-explanations-plugins`
- `calibrated-explanations-calibration`
- `calibrated-explanations-explanation`
- `calibrated-explanations-visualization`

If you are authoring or reviewing a plugin package rather than installing one,
start with the upstream plugin contract before changing scaffolded code.
To make a plugin official in this repository, it must be added to the matching
family metapackage dependencies.
