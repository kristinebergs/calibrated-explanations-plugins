# calibrated-explanations-explanation-factual-shap

Family: `explanation`

Purpose: Scaffolded official explanation plugin package aligned to the CE plugin contract.

Install:

```bash
pip install calibrated-explanations-explanation-factual-shap
```

Compatibility: `calibrated-explanations>=0.11`

Upstream docs:

- CE Read the Docs: <https://calibrated-explanations.readthedocs.io/en/latest/>
- Plugin contract: <https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html>

I’m mapping this to the plugin contracts and the current SHAP package structure first, so the plan is anchored to the actual CE extension points rather than a generic rewrite outline.

Read [](file:///c%3A/Users/loftuw/Documents/Github/calibrated-explanations-plugins/packages/explanation/calibrated-explanations-explanation-factual-shap/src/ce_explanation_factual_shap/plugin.py)

Read skill [ce-plugin-scaffold](file:///c%3A/Users/loftuw/.claude/skills/ce-plugin-scaffold/SKILL.md?vscodeLinkType%3Dskill#1-1), lines 1 to 240

Read [](file:///c%3A/Users/loftuw/Documents/Github/calibrated-explanations-plugins/packages/explanation/calibrated-explanations-explanation-factual-shap/README.md)

Read [](file:///c%3A/Users/loftuw/Documents/Github/calibrated-explanations-plugins/packages/explanation/calibrated-explanations-explanation-factual-shap/tests/test_factual_shap.py)

Read skill [ce-plotspec-author](file:///c%3A/Users/loftuw/.claude/skills/ce-plotspec-author/SKILL.md?vscodeLinkType%3Dskill#1-1), lines 1 to 240

# Re-implementation plan

The current SHAP package should be treated as a failed prototype. The rewrite starts by deleting the design centered on plugin.py, because that file is structurally wrong: it delegates to ordinary factual CE output and only appends SHAP as side metadata. The new implementation should not reuse that path.

**Target Contract**

1. The plugin must produce SHAP-first explanations, not CE rule explanations with SHAP attached.
2. Each explained instance must carry three additive attribution vectors: central prediction, lower bound, and upper bound.
3. The rendered rows must be feature names only, with no threshold conditions such as `<=`, `>`, or bin-derived rules.
4. The central explanation must reconcile to the calibrated prediction, and the lower/upper explanations must reconcile to the calibrated interval endpoints.
5. If a mode is not implemented correctly, the plugin must raise immediately rather than fallback.

**Implementation Plan**

1. **Delete the current explanation path completely.**  
Remove the use of `LegacyFactualExplanationPlugin`, remove `collection_to_batch`, and remove any call to `explain_factual(..., _use_plugin=False)` from plugin.py. That code path guarantees the wrong output type.

2. **Define the v1 scope explicitly before coding.**  
Do not try to support every task on day one. The defensible v1 is:
   - Binary classification: supported
   - Regression: optional second milestone
   - Multiclass classification: fail with `NotImplementedError` until class-target semantics are designed
This prevents shipping another semantically ambiguous plugin.

3. **Replace the current SHAP helper with bound-specific prediction adapters.**  
The new helper should expose three public callables over the CE prediction bridge:
   - `predict_center(x) -> calibrated point prediction`
   - `predict_lower(x) -> calibrated lower bound`
   - `predict_upper(x) -> calibrated upper bound`
These functions must be built from the CE runtime context, not private internals and not raw learner probabilities. The current helper in shap_helper.py only creates one SHAP explainer, which makes true lower/upper SHAP impossible.

4. **Create three SHAP explainers, not one.**  
For each supported task, instantiate:
   - one SHAP explainer for the calibrated center prediction,
   - one for the lower bound,
   - one for the upper bound.
The output of the plugin should be derived from those three attribution tensors. This is the core requirement you stated.

5. **Materialize a fast-style explanation payload instead of a factual-rule payload.**  
The plugin should use the same presentation semantics as `FastExplanation` in the core library:
   - `rule` values are just feature names,
   - `value` is the observed feature value,
   - `weight` is the central SHAP attribution,
   - `weight_low` is the lower-bound SHAP attribution,
   - `weight_high` is the upper-bound SHAP attribution.
The existing core `FastExplanation` shape in the CE library is the right conceptual target because it already avoids rule conditions and supports lower/high envelopes.

6. **Decide whether to reuse `FastExplanation` or add a plugin-local `ShapExplanation` subclass.**  
My recommendation:
   - First implementation: reuse the fast-style payload contract to minimize core churn.
   - If `FastExplanation` cannot faithfully express the SHAP base value and bound-specific reconstruction semantics, create a plugin-local `ShapExplanation` subclass with the same feature-only display model.
This decision should be made after a short spike against one binary classification example.

7. **Build explanation objects directly instead of hiding SHAP in metadata.**  
SHAP values must become the primary explanation object. Metadata may still exist for debugging, but it is secondary. The notebook symptom `"shap" in batch_metadata == False` becomes irrelevant once the explanation itself is SHAP-backed.

8. **Add a SHAP-specific plot path as a separate milestone.**  
Do not block the semantic rewrite on custom plotting. Sequence it like this:
   - Milestone A: correct data model, fast-style rendering, no conditions
   - Milestone B: SHAP-native plot builder using PlotSpec
For Milestone B, add an opt-in plot builder that renders:
   - waterfall for one instance,
   - bar summary for a single bound view,
   - explicit selector for center/lower/upper.
This should not silently replace CE default plotting until the output is stable.

9. **Rewrite the tests from behavior-first acceptance criteria.**  
Replace test_factual_shap.py entirely. New tests should assert:
   - no delegation to ordinary factual explanations,
   - no rule strings containing comparisons,
   - `rule` labels equal feature names,
   - one attribution vector each for center, lower, upper,
   - per-instance attribution length equals number of features,
   - SHAP additivity approximately reconstructs center/lower/upper outputs,
   - unsupported modes raise explicitly,
   - missing `shap` import fails immediately,
   - notebooks demonstrate true SHAP behavior.

10. **Rewrite the notebook after the code is correct, not before.**  
The notebook should become a validation artifact:
   - print the feature-only rows,
   - show central/lower/upper attribution tables,
   - prove there are no rule conditions,
   - optionally compare CE factual explanation versus SHAP plugin output side by side to show the semantic difference.

**Recommended Delivery Sequence**

1. Remove the current plugin implementation and replace it with a failing stub plus explicit scope guards.
2. Implement binary-classification center/lower/upper prediction adapters.
3. Build SHAP attribution generation and fast-style explanation materialization.
4. Add behavior-focused tests for no-conditions and lower/upper attribution correctness.
5. Add notebook validation.
6. Add SHAP-native plotting as a follow-up milestone.

**Acceptance Criteria**

1. Running the SHAP plugin does not call ordinary factual explanation generation.
2. The explanation rows are feature names only.
3. No threshold conditions appear anywhere in the explanation payload.
4. Each instance exposes central, lower, and upper SHAP contributions.
5. The contributions reconstruct the calibrated prediction interval endpoints within tolerance.
6. Unsupported scope fails explicitly.
7. The notebook shows materially different output from ordinary CE factual explanations.

If you want, I can turn this plan into an actionable rewrite backlog next: concrete tasks by file, replacement module layout, and the first test cases to write before any implementation.
