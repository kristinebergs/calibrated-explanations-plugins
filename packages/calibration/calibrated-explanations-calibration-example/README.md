# calibrated-explanations-calibration-example

Family: `calibration`

Purpose: Official example interval plugin showing the minimum wiring needed for
`CalibratedExplainer` to discover, trust, and use a third-party calibrator.

Install:

```bash
pip install calibrated-explanations-calibration-example
```

Compatibility: `calibrated-explanations>=0.11`

What this example demonstrates:

- `plugin_meta` declares the public plugin identifier and capabilities
- `register_example_interval_plugin()` registers the descriptor when CE loads the entry point
- `create(...)` delegates to CE's builtin legacy interval calibrator, so the package produces real calibrated outputs immediately

Runtime path:

1. Trust `official.calibration.example`
2. Let CE load entry-point plugins
3. Pass `interval_plugin="official.calibration.example"` into `CalibratedExplainer`
4. Call `predict(...)` or `predict_proba(...)`
