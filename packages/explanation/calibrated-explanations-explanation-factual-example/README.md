# calibrated-explanations-explanation-factual-example

Family: `explanation`

Status: `experimental`

> **Experimental**: this plugin has not completed a maturity review and is
> not published to PyPI. Install from source (see below).

Purpose: Example explanation plugin showing the minimum wiring needed
for `CalibratedExplainer` to discover, trust, initialize, and invoke a custom
explanation plugin.

Install:

```bash
git clone https://github.com/kristinebergs/calibrated-explanations-plugins.git
pip install ./calibrated-explanations-plugins/packages/explanation/calibrated-explanations-explanation-factual-example
```

Compatibility: `calibrated-explanations>=0.11`

What this example demonstrates:

- `plugin_meta` declares a factual explanation plugin with explicit task support
- optional provisional `plugin_meta["config_schema"]` declares runtime config keys
- `register_example_explanation_plugin()` registers the explanation descriptor during entry-point loading
- `initialize(...)` receives CE's runtime context and reads `context.plugin_config`
- `explain_batch(...)` delegates to CE's builtin factual plugin, so the package returns a real `ExplanationBatch`

Runtime path:

1. Trust `official.explanation.factual.example`
2. Let CE load entry-point plugins
3. Optionally provide provisional config under `[tool.calibrated_explanations.plugin_configs."official.explanation.factual.example"]`
4. Pass `factual_plugin="official.explanation.factual.example"` into `CalibratedExplainer`
5. Call `explain_factual(...)`

The config schema and `context.plugin_config` field are a provisional hardening
surface for OSS CE, CEE, and official plugin validation. They are not yet a
compatibility-frozen plugin config standard.
