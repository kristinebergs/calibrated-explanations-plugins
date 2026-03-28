# calibrated-explanations-explanation-alternative-example

Family: `explanation`

Purpose: Official example alternative explanation plugin showing how
`CalibratedExplainer` discovers, trusts, initializes, and invokes an
alternative explanation plugin.

Install:

```bash
pip install calibrated-explanations-explanation-alternative-example
```

Compatibility: `calibrated-explanations>=0.11`

What this example demonstrates:

- `plugin_meta` declares an alternative explanation plugin with explicit task support
- `register_alternative_example_plugin()` registers the explanation descriptor during entry-point loading
- `initialize(...)` receives CE's explanation context
- `explain_batch(...)` delegates to CE's builtin alternative explainer so the package returns real alternative explanations

Runtime path:

1. Trust `official.explanation.alternative.example`
2. Let CE load entry-point plugins
3. Pass `alternative_plugin="official.explanation.alternative.example"` into `CalibratedExplainer`
4. Call `explore_alternatives(...)`

Upstream docs:

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- Plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>
