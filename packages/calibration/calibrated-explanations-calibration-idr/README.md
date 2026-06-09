# calibrated-explanations-calibration-idr

Install this plugin package with `calibrated-explanations` in a Python `>=3.13` environment:

```bash
pip install calibrated-explanations-calibration-idr
```

Family: `calibration`

Purpose: post-hoc IDR regression distribution calibration for `calibrated-explanations`, using the
upstream `isodistrreg.IDR` Python bindings.

Compatibility: `calibrated-explanations>=0.11`; Python `>=3.13`. The upstream Python
`isodistrreg` bindings currently require Python `>=3.13`, and this plugin has no alternate IDR
backend.


A CI-tested source-install command for the upstream backend is:

```bash
python -m pip install \
  "isodistrreg @ git+https://github.com/AlexanderHenzi/isodistrreg.git@324d85a6e83c4c44c9fde1c29d0a2b743776096e#subdirectory=bindings/python"
```

That command fails on Python 3.12 with `Package 'isodistrreg' requires a different Python`;
create or activate a Python 3.13 environment before installing the backend.

This package provides `IDRRegressionIntervalCalibratorPlugin`, an interval calibrator plugin for
ordinary regression and thresholded/probabilistic regression. Use it as the CE interval calibrator:
the underlying learner is fitted by CE through `explainer.fit(...)` or supplied pre-fitted, and the
plugin is fitted during `explainer.calibrate(...)` from calibration pairs of raw learner predictions
and observed targets.

Ordinary regression returns calibrated y-space quantiles from `isodistrreg.IDR`. The primary
`predict` field is the calibrated distribution median, not the raw learner prediction; `raw_predict`
is diagnostic metadata only. Thresholded regression computes IDR event scores, then delegates final
probability interval calibration to CE's Venn-Abers implementation through a stable CE context
factory. Metadata declares this as the `binary_event_probability_interval` role with
`official.calibration.venn_abers` as the default probability interval calibrator.

Do **not** call `model.fit(...)` and `explainer.fit(...)` on the same model instance. Use either CE
owned fitting or a pre-fitted model, as shown in the example notebook.

The plugin has exactly one IDR backend: upstream `isodistrreg.IDR`. It does not use
`sklearn.isotonic.IsotonicRegression` and does not silently fall back to CE's legacy regression
calibrator. Since upstream `isodistrreg` is GPL-2.0-or-later and may not be available as a normal
PyPI dependency for all supported environments, review licensing and packaging policy before
promoting this package into an official metapackage.
