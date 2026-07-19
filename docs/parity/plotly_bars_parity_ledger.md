# Plotly `*_bars` Parity Ledger

**Last updated:** 2026-07-19 (commit range f4b9a2b → 0.3.2 re-audit)  
**Source of truth:** PlotSpec / matplotlib adapter (`calibrated_explanations.viz`)  
**Plotly renderers:** `ce_visualization_plotly.factual_bars`, `ce_visualization_plotly.alternative_bars`

---

## Parity method

Identical to the method used for legacy vs PlotSpec in `calibrated_explanations/`:

### 1. Side-by-side visual report (human review)

`scripts/plot_parity/generate_side_by_side.py` (mirrors `calibrated_explanations/scripts/plot_spec/generate_side_by_side.py`):
- Renders each fixture via PlotSpec → matplotlib → saves `*_plotspec.png`
- Renders the same fixture via Plotly plugin → saves `*_plotly.html` (and `*_plotly.png` if kaleido is installed)
- Output goes to `reports/plot_parity/plotspec_vs_plotly_bars/` for human review

Run:
```bash
python scripts/plot_parity/generate_side_by_side.py [--output-dir DIR] [--tag v0.x.y]
```

### 2. Automated primitive comparison (CI)

`tests/parity/test_plotly_bars_parity.py` (mirrors `calibrated_explanations/tests/unit/viz/test_alternative_regression_parity.py`):
- Same fixture parameters fed to both the PlotSpec builder and the Plotly plugin via `FakeExplanation`
- PlotSpec path: `build_*_spec()` → `mpl_adapter.render(export_drawn_primitives=True)` → structured primitives dict
- Plotly path: `FakeExplanation` → `LocalFactualBarsPlotBuilder.build(context)` + `render()` → `go.Figure` → extracted primitives dict
- Field-by-field assertions with `pytest.approx` numeric tolerance and exact hex color comparison
- 24 tests passing across 5 cases (3 factual × 3 factual tests + 3 alternative × 4 tests + 1 cross-0.5 test)

---

## Legend

| Status | Meaning |
|---|---|
| ✅ CLOSED | Fixed in this session or previously confirmed aligned |
| ⚠️ WATCH | Likely acceptable; needs a parity test to confirm |
| ❌ GAP | Known remaining discrepancy — action required |

---

## Factual bars (`plotly.local.factual_bars`)

| ID | Primitive | PlotSpec / legacy | Plotly (after this session) | Status |
|---|---|---|---|---|
| BARS-001 | Public API routing | `filter_top` forwarded; `filename` → `.html` | Same | ✅ CLOSED |
| BARS-002 | `uncertainty` parameter | Public `uncertainty=True`; one-sided raises `Warning` | Bridge maps `uncertainty` → `show_uncertainty`; raises same `Warning` | ✅ CLOSED |
| BARS-003 | Factual ranking | `rank_features` + `calculate_metrics`; ties broken by interval width | `_compute_ranking` calls CE `rank_features` + `calculate_metrics`; same tie-break | ✅ CLOSED |
| BARS-006 | Hover on solid bars | N/A (matplotlib has no hover) | `hovertext` + `hovertemplate` on every contribution `go.Bar` | ✅ CLOSED (intentional extension) |
| BARS-007 | Hover on header bars | N/A | `hovertext` + `hovertemplate` on every header trace | ✅ CLOSED (intentional extension) |
| BARS-009 | Draw order: uncertainty shadows solid | `fill_betweenx` solid first, overlay after → overlay on top | Solid `go.Bar` added first, uncertainty `go.Bar` added after; `barmode="overlay"` → last trace on top ✅ | ✅ CLOSED |
| BARS-010 | Zero-crossing interval split | Solid suppressed; overlay split neg/pos | Solid suppressed; interval split into neg/pos entries | ✅ CLOSED |
| BARS-011 | Body x-range | `xlim` from solids + intervals + 5% padding (dual header) | `_compute_body_xrange` mirrors same logic | ✅ CLOSED |
| BARS-012 | Regression body x-range | Exact `[x_min, x_max]` without padding | Same | ✅ CLOSED |
| BARS-013 | Same min/max within each panel | Header uses `[0,1]`; body uses contribution range | Separate axes per panel; each range applied to its axis only | ✅ CLOSED |
| BARS-017 | Factual bar colors | mpl adapter draws `red`/`blue` (`#ff0000`/`#0000ff`); overlays same hue at alpha 0.2 | Constants set to the exact mpl hues; overlays rgba alpha 0.20 | ✅ CLOSED (0.3.2) — `test_factual_bars_solid_colors_match_plotspec`, `test_factual_bars_overlay_colors_match_plotspec` compare against exported mpl primitives |
| BARS-021 | Threshold x-labels | Scalar: `P(y<=t)`/`P(y>t)` with `.2f`; interval: `{lo} < y_hat <= {hi}` with `.3f`; binary fallback `P(y=1)`/`P(y=0)`; class labels `P(y=<label>)` | Caption block rewritten to CE's `plotting.py` contract (lowercase `y`, exact precision, all branches) | ✅ CLOSED (0.3.2) — caption unit tests in `test_factual_bars.py` |
| BARS-022 | Right-side instance values | Twin y-axis titled "Instance values" | **Secondary y-axis `yaxis2`/`yaxis3`** overlaying body axis; `ticktext=instance_values`, title "Instance values" | ✅ CLOSED (this session) |
| BARS-023 | Bar width | `fill_betweenx` at `y ± 0.2` → height 0.4 | `width=0.4` on all solid + uncertainty `go.Bar` traces; `bargap` removed | ✅ CLOSED (this session) |
| BARS-024 | Plot title | No visible title | Empty title string | ✅ CLOSED |

---

## Alternative bars (`plotly.local.alternative_bars`)

| ID | Primitive | PlotSpec / legacy | Plotly (after this session) | Status |
|---|---|---|---|---|
| BARS-004 | Alternative ranking | CE `rank_features` + `calculate_metrics`; flip when base ≤ 0.5; reverse | `_rank_items` now calls CE's public `rank_features`/`calculate_metrics` (unbound public implementation when the payload lacks the method); flip at base ≤ 0.5; identical-to-base drop via `np.isclose`; no inline replica | ✅ CLOSED (0.3.2) — `tests/parity/test_alternative_ranking_parity.py` (13 hand-computed oracle cases) |
| BARS-005 | Identical-to-base filtering | Rank → filter_top → drop identical | Same order | ✅ CLOSED |
| BARS-008 | Hover on interval bars | N/A | `hovertext` on every interval segment trace and marker | ✅ CLOSED (intentional extension) |
| BARS-014 | Probabilistic interval split at 0.5 | `_build_probability_segments` splits when `lo < 0.5 < hi` | **Split logic added**: segments split at `pivot` with `_ce_fill_color(lo/hi, 0.99)` per half | ✅ CLOSED (this session) |
| BARS-015 | Base interval split at 0.5 | Base vrect split at pivot | vrect split at pivot using `_ce_fill_color(eff_lo/eff_hi, 0.15)` | ✅ CLOSED (this session) |
| BARS-016 | Alternative bar colors | `_legacy_get_fill_color(predict, 0.99)` per segment | `_ce_fill_color` — inline canonical copy (the CE original is private and is used only as a test oracle; see `test_inline_fill_color_matches_ce_legacy_implementation`) | ✅ CLOSED |
| BARS-016b | Base interval color | `_legacy_get_fill_color(base_predict, 0.15)` | **Now uses `_ce_fill_color(center, 0.15)`** / `_REGRESSION_BASE_COLOR` | ✅ CLOSED (this session) |
| BARS-018 | Alternative regression x-range | `y_minmax` when available; else base-interval bounds; no 5% margin | **5% margin removed**; fallback now uses `(base_low, base_high)` exactly like `build_alternative_regression_spec` | ✅ CLOSED (this session) |
| BARS-019 | Alternative regression base line | `REGRESSION_BAR_COLOR`, solid, alpha=0.3, linewidth=2 | **Changed**: solid `line_dash="solid"`, `line_color=_REGRESSION_BAR_COLOR`, `opacity=0.3`, `line_width=2` | ✅ CLOSED (this session) |
| BARS-020 | Threshold label precision | Scalar `.2f`, interval `.3f` | **Fixed**: `f"{thr:.2f}"` / `f"{t0:.3f} and {t1:.3f}"` | ✅ CLOSED (this session) |
| BARS-022 | Right-side instance values | Twin y-axis titled "Instance values" | **Secondary `yaxis2`** added with `ticktext=instance_values`, title "Instance values" | ✅ CLOSED (this session) |
| BARS-023 | Bar width | `fill_betweenx` at `y ± 0.2` → height 0.4 | **`width=0.4`** on every `go.Bar` interval trace | ✅ CLOSED (this session) |
| BARS-025 | `show_uncertainty` for alternatives | No public toggle; intervals always shown | Passing the option now emits a visible `UserWarning` + INFO log stating it has no effect; README documents it as ignored | ✅ CLOSED (0.3.2) |

---

## Remaining open gaps

None. All GAP and WATCH items are closed as of the 0.3.2 re-audit
(2026-07-19). Two defects fixed while closing BARS-004 deserve mention:

- The previous inline `_rank_items` scored ensured ranking as
  `w·p + (1−w)·width` (preferring **wide** intervals); CE's
  `calculate_metrics` scores `(1−w)·(1−width) + w·p` (preferring **narrow**
  intervals) — orderings genuinely diverged at the default `rnk_weight=0.5`.
- The classification flip fired at `base < 0.5`; CE flips at `base ≤ 0.5`.
  Identical-to-base rows are now dropped with CE's `np.isclose` tolerances
  (previously a much stricter 1e-10 absolute cutoff).

`factual_bars._compute_ranking` likewise no longer keeps an inline replica:
both bar styles call CE's public `rank_features`/`calculate_metrics` and let
failures propagate.

---

## Parity test coverage (implemented)

Primitive tests live in `tests/parity/test_plotly_bars_parity.py`
(counts below verified 2026-07-19, dev environment, Python 3.11.9, CE
1.0.0rc1, `python -m pytest tests/parity -q`: 43 passed, 2 intentional
skips — cases with no interval bars/overlays). Ranking-semantics tests live
in `tests/parity/test_alternative_ranking_parity.py` (13 passed).

### Factual bars tests

| Test | Cases | Status |
|---|---|---|
| `test_factual_bars_row_count_matches_plotspec` | zero_crossing, no_uncertainty, regression | ✅ 3 pass |
| `test_factual_bars_labels_match_plotspec` | zero_crossing, no_uncertainty, regression | ✅ 3 pass |
| `test_factual_bars_all_widths_are_04` | zero_crossing, no_uncertainty, regression | ✅ 3 pass |
| `test_factual_bars_uncertainty_overlays_drawn_after_solid` | zero_crossing, regression | ✅ 2 pass, 1 skip (no interval) |
| `test_factual_bars_solid_colors_match_plotspec` | all 3 cases | ✅ 3 pass |
| `test_factual_bars_overlay_colors_match_plotspec` | zero_crossing, regression | ✅ 2 pass, 1 skip (no overlays) |

### Alternative bars tests

| Test | Cases | Status |
|---|---|---|
| `test_alternative_bars_item_count_matches_plotspec` | cross_05, both_below_05, regression | ✅ 3 pass |
| `test_alternative_bars_all_widths_are_04` | cross_05, both_below_05, regression | ✅ 3 pass |
| `test_alternative_bars_xlim_matches_plotspec` | cross_05, both_below_05, regression | ✅ 3 pass |
| `test_alternative_bars_base_interval_vrect_present` | cross_05, both_below_05, regression | ✅ 3 pass |
| `test_alternative_probabilistic_cross_05_produces_two_bar_segments` | cross_05 | ✅ 1 pass |

---

## Intentional extensions (allowed Plotly-only features)

| Feature | All traces affected |
|---|---|
| Hover cards (default on) | Every `go.Bar` and `go.Scatter` trace carries `hovertext` + `hovertemplate` |
| HTML output | Rendered to `.html` via `figure.write_html()` instead of static image |
| Interactive zoom/pan | Plotly default; no equivalent in matplotlib |
