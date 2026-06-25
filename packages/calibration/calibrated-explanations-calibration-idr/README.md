# calibrated-explanations-calibration-idr

Install this plugin package with `calibrated-explanations` in a Python `>=3.13` environment:

```bash
pip install calibrated-explanations-calibration-idr
```

Family: `calibration`

Purpose: post-hoc IDR regression distribution calibration for `calibrated-explanations`, using the
upstream `isodistrreg.IDR` Python bindings. Two plugins are provided:

- **`official.calibration.idr_regression`** — plain IDR distribution quantiles (not conformal).
- **`official.calibration.conformal_idr_regression`** — IDR quantiles with a split-conformal
  correction that provides finite-sample marginal coverage under exchangeability.

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

## Plain IDR (`official.calibration.idr_regression`)

This plugin provides `IDRRegressionIntervalCalibratorPlugin`. It returns IDR distribution
quantiles directly and is **not conformal**. There is no finite-sample coverage guarantee.

```python
from ce_calibration_idr import IDRRegressionIntervalCalibratorPlugin
from calibrated_explanations import WrapCalibratedExplainer

explainer = WrapCalibratedExplainer(model)
explainer.fit(X_train, y_train)
explainer.calibrate(X_cal, y_cal, interval_plugin=IDRRegressionIntervalCalibratorPlugin())
```

## Conformal IDR (`official.calibration.conformal_idr_regression`)

This plugin provides `ConformalIDRRegressionIntervalCalibratorPlugin`. It adds a held-out
split-conformal correction on top of IDR quantiles.

**Guarantee**: finite-sample marginal coverage under exchangeability of held-out calibration
examples and future test examples. This is a marginal guarantee only — conditional coverage is
not claimed. Calibration/test distribution shift invalidates the conformal guarantee.

**What conformal IDR does not claim**:
- IDR itself does not have conformal validity; the guarantee comes from the held-out correction.
- Poor or biased IDR fit does not invalidate marginal conformal coverage, but it can make
  intervals wide or locally inefficient.

### Preferred usage (external IDR-fit data)

Supply `idr_X` and `idr_y` (typically the training set). IDR is fitted on this external data
and the full CE calibration set is used for conformal correction:

```python
from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin
from calibrated_explanations import WrapCalibratedExplainer
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor(random_state=0)
explainer = WrapCalibratedExplainer(model)
explainer.fit(X_train, y_train)

plugin = ConformalIDRRegressionIntervalCalibratorPlugin(
    idr_X=X_train,
    idr_y=y_train,
    random_state=0,
)
explainer.calibrate(X_cal, y_cal, interval_plugin=plugin)
```

### Fallback usage (internal calibration split)

When `idr_X`/`idr_y` are omitted, the CE calibration set is split internally. This uses part
of the calibration data for IDR fitting and the remainder for conformal correction, so it is
less efficient when calibration data is scarce:

```python
explainer.calibrate(
    X_cal,
    y_cal,
    interval_plugin="official.calibration.conformal_idr_regression",
)
```

Or with explicit parameters:

```python
from ce_calibration_idr import ConformalIDRRegressionIntervalCalibratorPlugin

plugin = ConformalIDRRegressionIntervalCalibratorPlugin(
    idr_fraction=0.5,   # fraction of cal set used for IDR fitting
    random_state=42,
)
explainer.calibrate(X_cal, y_cal, interval_plugin=plugin)
```

### Threshold mode

Both plugins support threshold mode. Threshold mode returns **probability intervals**, not
y-space intervals. The IDR distribution is used to compute event scores, and CE's Venn-Abers
implementation calibrates the final probability intervals:

- Scalar threshold `t`: event is `Y <= t`.
- Tuple threshold `(lower, upper)`: event is `lower <= Y <= upper`.

For the conformal plugin, Venn-Abers is always fitted on held-out data not used for IDR fitting:
- With external IDR data: the full CE calibration set is available for Venn-Abers.
- With fallback split: only the held-out split is used for Venn-Abers.

## Interval types summary

| Plugin | Ordinary regression interval | Threshold interval |
|---|---|---|
| `idr_regression` | IDR quantiles (not conformal) | Venn-Abers on IDR event scores |
| `conformal_idr_regression` | IDR quantiles + conformal correction | Venn-Abers on IDR event scores |

## Evaluation

Run the local parity and speed comparison against CE's default CPS regression calibrator with:

```bash
python evaluation/compare_idr_cps.py --samples 400 --repeats 5
```

The evaluation trains one underlying regression model, reuses that fitted model state for all
calibrators, and reports empirical coverage, interval widths, qhat, conformal calibration set
sizes, interval validity, and prediction timings for:

- CE default CPS regression intervals
- Plain IDR intervals
- Conformal IDR intervals with external IDR data
- Conformal IDR intervals with internal calibration split

Empirical coverage in this evaluation is a regression test and sanity check only; it is not
proof of validity.

The plugin has exactly one IDR backend: upstream `isodistrreg.IDR`. It does not use
`sklearn.isotonic.IsotonicRegression` and does not silently fall back to CE's legacy regression
calibrator. Since upstream `isodistrreg` is GPL-2.0-or-later and may not be available as a normal
PyPI dependency for all supported environments, review licensing and packaging policy before
promoting this package into an official metapackage.
