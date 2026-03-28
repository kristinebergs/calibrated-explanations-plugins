# calibrated-explanations-visualization-example

Family: `visualization`

Purpose: Official example visualization plugin showing how a CE plot package
boots a builder, renderer, and style into the runtime registry.

Install:

```bash
pip install calibrated-explanations-visualization-example
```

Compatibility: `calibrated-explanations[viz]>=0.11`

What this example demonstrates:

- a bootstrap entry point in `calibrated_explanations.plugins`
- a PlotSpec builder entry point
- a PlotSpec renderer entry point
- style registration tying `official.example` to the builder and renderer identifiers

Runtime path:

1. Trust `official.visualization.example.bootstrap`, `official.visualization.example.builder`, and `official.visualization.example.renderer`
2. Let CE load entry-point plugins
3. Generate explanations with `CalibratedExplainer`
4. Call `plot(style="official.example")`
