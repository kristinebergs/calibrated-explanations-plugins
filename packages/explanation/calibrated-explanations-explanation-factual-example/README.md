# calibrated-explanations-explanation-factual-example

Family: `explanation`

Purpose: Official example explanation plugin showing the minimum wiring needed
for `CalibratedExplainer` to discover, trust, initialize, and invoke a custom
explanation plugin.

Install:

```bash
pip install calibrated-explanations-explanation-factual-example
```

Compatibility: `calibrated-explanations>=0.11`

What this example demonstrates:

- `plugin_meta` declares a factual explanation plugin with explicit task support
- `register_example_explanation_plugin()` registers the explanation descriptor during entry-point loading
- `initialize(...)` receives CE's runtime context
- `explain_batch(...)` delegates to CE's builtin factual plugin, so the package returns a real `ExplanationBatch`

Runtime path:

1. Trust `official.explanation.factual.example`
2. Let CE load entry-point plugins
3. Pass `factual_plugin="official.explanation.factual.example"` into `CalibratedExplainer`
4. Call `explain_factual(...)`
