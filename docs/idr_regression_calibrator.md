# IDR regression calibrator

`calibrated-explanations-calibration-idr` provides a post-hoc regression distribution
calibrator backed by the upstream `isodistrreg.IDR` Python bindings from
`AlexanderHenzi/isodistrreg`. It does **not** replace the underlying regression learner.
The underlying learner is fitted by CE through `explainer.fit(...)` or supplied pre-fitted.
The IDR plugin is fitted during `explainer.calibrate(...)`, using calibration-set pairs of
raw learner predictions and observed targets.

For ordinary regression, the plugin returns calibrated y-space quantiles from `isodistrreg.IDR`.
The primary `predict` field is the calibrated distribution median, not the raw model prediction.
`raw_predict` is diagnostic metadata only.

For thresholded/probabilistic regression, the plugin computes event scores from the calibrated
IDR distribution, but probability intervals are still produced by CE's Venn-Abers calibrator. The
CE context must provide a stable Venn-Abers factory; this plugin does not dynamically import CE
internals or implement its own probability interval method. Plugin metadata declares that
threshold mode requires a binary event probability interval calibrator and defaults that role to
`official.calibration.venn_abers`.

Therefore:
- regression low/high are y-space bounds;
- thresholded low/high are probability bounds;
- predict is always the final calibrated prediction.

## CE lifecycle

Use the plugin as an interval calibrator, not as the wrapped model.

Valid pattern A: CE owns fitting of the underlying model.

```python
model = RandomForestRegressor(random_state=0)
explainer = WrapCalibratedExplainer(model)
explainer.fit(X_train, y_train)
explainer.calibrate(
    X_cal,
    y_cal,
    interval_calibrator="official.calibration.idr_regression",
)
```

Valid pattern B: the model is already fitted. Do not call `explainer.fit(...)`.

```python
model = RandomForestRegressor(random_state=0).fit(X_train, y_train)
explainer = WrapCalibratedExplainer(model)
explainer.calibrate(
    X_cal,
    y_cal,
    interval_calibrator="official.calibration.idr_regression",
)
```

Invalid pattern: do not call `model.fit(...)` and `explainer.fit(...)` on the same model instance.

## Backend and packaging status

The upstream Python bindings for `isodistrreg` exist and expose `isodistrreg.IDR`, which this plugin
uses as its only IDR backend. Those bindings currently require Python `>=3.13`, are GPL-2.0-or-later,
and may be distributed as GitHub Action wheel artifacts or built from the upstream repository rather
than as a normal PyPI dependency. For that reason this plugin package declares Python `>=3.13`,
intentionally does not list `isodistrreg` as a normal PyPI dependency in `pyproject.toml`, and
runtime use requires installing a compatible upstream backend.


A CI-tested source-install command for the upstream backend is:

```bash
python -m pip install \
  "isodistrreg @ git+https://github.com/AlexanderHenzi/isodistrreg.git@324d85a6e83c4c44c9fde1c29d0a2b743776096e#subdirectory=bindings/python"
```

That command fails on Python 3.12 with `Package 'isodistrreg' requires a different Python`;
create or activate a Python 3.13 environment before installing the backend.

Install a compatible upstream `isodistrreg` build before using the plugin. Do not substitute
`sklearn.isotonic.IsotonicRegression`: it is not IDR and does not produce conditional predictive
distributions.

Because `isodistrreg` is GPL-2.0-or-later, redistributors should review whether depending on it is
compatible with their distribution and licensing policy before publishing wheels or metapackages.
The package remains outside the official calibration metapackage until dependency, wheel, licensing,
and protocol-conformance questions are resolved.

> **Warning**
>
> IDR intervals are not conformal predictive-system intervals. Do not claim exchangeability-based
> finite-sample conformal coverage unless an additional conformal validity layer is added.

See `packages/calibration/calibrated-explanations-calibration-idr/examples/idr_regression_calibrator.ipynb`
for the canonical usage notebook.
