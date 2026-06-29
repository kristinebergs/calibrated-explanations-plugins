"""Generate side-by-side PlotSpec and Plotly renders for *_bars parity review.

Mirrors calibrated_explanations/scripts/plot_spec/generate_side_by_side.py.

Usage (from the repo root):
    python scripts/plot_parity/generate_side_by_side.py [--output-dir <dir>]

Output goes to reports/plot_parity/plotspec_vs_plotly_bars/<tag>/ by default.
Each case produces:
  - <case>_plotspec.png   (matplotlib render via mpl_adapter)
  - <case>_plotly.html    (Plotly interactive HTML render)
  - <case>_plotly.png     (Plotly static PNG — requires kaleido; skipped if absent)

Human review rule:
  Open the paired files for each case and confirm visual parity.
  Permitted differences: hover cards, interactive controls (zoom/pan).
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

# ---------------------------------------------------------------------------
# Sys-path bootstrapping: allow running from repo root without install
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CE_SRC = (
    _REPO_ROOT.parent / "calibrated_explanations" / "src"
)
_PLUGIN_SRC = (
    _REPO_ROOT
    / "packages"
    / "visualization"
    / "calibrated-explanations-visualization-plotly"
    / "src"
)
for _p in [str(_CE_SRC), str(_PLUGIN_SRC)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("MPLBACKEND", "Agg")

# ---------------------------------------------------------------------------
# Imports from CE core (PlotSpec builders + matplotlib adapter)
# ---------------------------------------------------------------------------
import calibrated_explanations.plugins.registry as _registry  # noqa: E402, I001
from calibrated_explanations.viz import (  # noqa: E402
    build_alternative_probabilistic_spec,
    build_alternative_regression_spec,
    build_probabilistic_bars_spec,
    build_regression_bars_spec,
    matplotlib_adapter as mpl_adapter,
)

_BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"
_FACTUAL_BUILDER_ID = "official.visualization.plotly.local.factual_bars.builder"
_FACTUAL_RENDERER_ID = "official.visualization.plotly.local.factual_bars.renderer"
_ALT_BUILDER_ID = "official.visualization.plotly.local.alternative_bars.builder"
_ALT_RENDERER_ID = "official.visualization.plotly.local.alternative_bars.renderer"
_FACTUAL_STYLE = "plotly.local.factual_bars"
_ALT_STYLE = "plotly.local.alternative_bars"

os.environ["CE_TRUST_PLUGIN"] = ",".join([
    "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap",
    _BOOTSTRAP_ID,
    _FACTUAL_BUILDER_ID,
    _FACTUAL_RENDERER_ID,
    _ALT_BUILDER_ID,
    _ALT_RENDERER_ID,
])

from ce_visualization_plotly.plugin import (  # noqa: E402
    register_plotly_visualization_components,
)

reset_fn = getattr(_registry, "reset_plugin_catalog", None)
if callable(reset_fn):
    reset_fn(kind="all")
register_plotly_visualization_components()

from calibrated_explanations.plugins.plots import PlotRenderContext  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixture parameters (same numbers used by test_plot_parity_fixtures.py)
# ---------------------------------------------------------------------------

_FACTUAL_PROB = {
    "predict": {"predict": 0.5, "low": 0.4, "high": 0.6},
    "feature_weights": {
        "predict": [0.05, 0.18, -0.12],
        "low": [-0.05, 0.12, -0.20],
        "high": [0.12, 0.25, -0.05],
    },
    "features_to_plot": [0, 1, 2],
    "column_names": ["f0", "f1", "f2"],
    "instance": [1.0, 2.0, 3.0],
    "y_minmax": [0.0, 1.0],
    "interval": True,
    "neg_caption": "P(y=0)",
    "pos_caption": "P(y=1)",
}

_FACTUAL_MULTICLASS = {
    "predict": {"predict": 0.65, "low": 0.55, "high": 0.75},
    "feature_weights": {
        "predict": [0.10, 0.20, -0.08],
        "low": [0.05, 0.14, -0.15],
        "high": [0.15, 0.28, -0.03],
    },
    "features_to_plot": [0, 1, 2],
    "column_names": ["f0", "f1", "f2"],
    "instance": [4.2, 1.5, 7.0],
    "y_minmax": [0.0, 1.0],
    "interval": True,
    "class_names": ["cat", "dog", "bird"],
    "predicted_class": 2,
}

_ALT_MULTICLASS = {
    "predict": {"predict": 0.55, "low": 0.45, "high": 0.65},
    "feature_weights": {
        "predict": [0.3, 0.7],
        "low": [0.2, 0.6],
        "high": [0.4, 0.8],
    },
    "features_to_plot": [0, 1],
    "column_names": ["a0", "a1"],
    "instance": [0.3, 0.8],
    "y_minmax": [0.0, 1.0],
    "interval": True,
    "class_names": ["cat", "dog", "bird"],
    "predicted_class": 2,
}

_FACTUAL_REG = {
    "predict": {"predict": 3.6, "low": 3.2, "high": 4.1},
    "feature_weights": {
        "predict": [0.25, -0.1],
        "low": [0.2, -0.15],
        "high": [0.3, -0.05],
    },
    "features_to_plot": [0, 1],
    "column_names": ["r0", "r1"],
    "instance": [2.3, 0.5],
    "y_minmax": [-5.0, 100.0],
    "interval": True,
}

_ALT_PROB = {
    "predict": {"predict": 0.6, "low": 0.45, "high": 0.65},
    "feature_weights": {
        "predict": [0.3, 0.7],
        "low": [0.2, 0.6],
        "high": [0.4, 0.8],
    },
    "features_to_plot": [0, 1],
    "column_names": ["a0", "a1"],
    "instance": [0.1, 0.2],
    "y_minmax": [0.0, 1.0],
    "interval": True,
}

_ALT_REG = {
    "predict": {"predict": 1.2, "low": 0.5, "high": 2.0},
    "feature_weights": {
        "predict": [0.9, -0.2],
        "low": [0.8, -0.4],
        "high": [1.0, 0.1],
    },
    "features_to_plot": [0, 1],
    "column_names": ["r0", "r1"],
    "instance": [0.5, -1.2],
    "y_minmax": [-1.0, 2.5],
    "interval": True,
}


# ---------------------------------------------------------------------------
# PlotSpec render → matplotlib PNG
# ---------------------------------------------------------------------------

def _render_plotspec_png(spec, output_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    mpl_adapter.render(spec, show=False, save_path=str(output_path.with_suffix("")))
    # adapter saves with suffix; if it did not produce the file, fall back to savefig
    if not output_path.exists():
        fig = mpl_adapter.render(spec, show=False, return_fig=True)
        if fig is not None:
            fig.savefig(str(output_path), dpi=120, bbox_inches="tight")
            plt.close(fig.number)


# ---------------------------------------------------------------------------
# FakeExplanation helpers — bridge PlotSpec fixture params to Plotly plugin
# ---------------------------------------------------------------------------

def _fw(params: dict, key: str) -> list:
    fw = params["feature_weights"]
    if isinstance(fw, dict):
        return list(fw.get(key, fw.get("predict", [])))
    return list(fw)


def _factual_fake_explanation(params: dict, *, task: str) -> SimpleNamespace:
    predict = params["predict"]
    feature_weights = params["feature_weights"]
    column_names = params["column_names"]
    features_to_plot = params["features_to_plot"]
    instance = params["instance"]
    class_names = params.get("class_names")
    predicted_class = params.get("predicted_class")

    if isinstance(feature_weights, dict):
        weights = feature_weights["predict"]
        weight_lows = feature_weights.get("low", weights)
        weight_highs = feature_weights.get("high", weights)
    else:
        weights = list(feature_weights)
        weight_lows = weights
        weight_highs = weights

    rules = {
        "weight": list(weights),
        "weight_low": list(weight_lows),
        "weight_high": list(weight_highs),
        "rule": list(column_names),
        "feature": list(features_to_plot),
        "value": list(instance),
        "feature_value": list(instance),
    }

    y_minmax = params.get("y_minmax")
    collection = SimpleNamespace(
        feature_names=list(column_names),
        y_minmax=y_minmax,
    )
    if class_names:
        collection.get_class_labels = lambda: class_names  # type: ignore[assignment]
    neg_caption = params.get("neg_caption")
    pos_caption = params.get("pos_caption")
    _classes = predicted_class if predicted_class is not None else (1 if task != "regression" else None)
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={
            "predict": predict["predict"],
            "low": predict.get("low"),
            "high": predict.get("high"),
            "classes": _classes,
        },
        rules=rules,
        get_mode=lambda: task,
        is_regression=lambda: task == "regression",
        is_probabilistic=lambda: task != "regression",
        is_alternative=lambda: False,
        neg_caption=neg_caption,
        pos_caption=pos_caption,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": task, "mode": task}
    return collection


def _alternative_fake_explanation(params: dict, *, task: str) -> SimpleNamespace:
    predict = params["predict"]
    feature_weights = params["feature_weights"]
    column_names = params["column_names"]
    features_to_plot = params["features_to_plot"]
    instance = params["instance"]
    y_minmax = params.get("y_minmax")
    class_names = params.get("class_names")
    predicted_class = params.get("predicted_class")

    if isinstance(feature_weights, dict):
        predicts = feature_weights["predict"]
        pred_lows = feature_weights.get("low", predicts)
        pred_highs = feature_weights.get("high", predicts)
    else:
        predicts = list(feature_weights)
        pred_lows = predicts
        pred_highs = predicts

    rules = {
        "rule": list(column_names),
        "predict": list(predicts),
        "predict_low": list(pred_lows),
        "predict_high": list(pred_highs),
        "feature": list(features_to_plot),
        "value": list(instance),
        "feature_value": list(instance),
    }

    collection = SimpleNamespace(
        feature_names=list(column_names),
        y_minmax=y_minmax,
    )
    if class_names:
        collection.get_class_labels = lambda: class_names  # type: ignore[assignment]
    _classes = predicted_class if predicted_class is not None else None
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={
            "predict": predict["predict"],
            "low": predict.get("low"),
            "high": predict.get("high"),
            "classes": _classes,
        },
        rules=rules,
        get_mode=lambda: task,
        is_regression=lambda: task == "regression",
        is_probabilistic=lambda: task != "regression",
        is_alternative=lambda: True,
        has_conjunctive_rules=False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": task, "mode": task}
    return collection


# ---------------------------------------------------------------------------
# Pre-ranking helpers — make PlotSpec row order match Plotly's ranking
# ---------------------------------------------------------------------------

def _sorted_features_for_plotspec_factual(params: dict) -> list[int]:
    """Return features_to_plot sorted ascending by |weight|.

    PlotSpec renders items in this order then inverts the y-axis, putting
    the highest-weight feature at the top — exactly matching Plotly's ranking.
    """
    fw = params["feature_weights"]
    indices = list(params["features_to_plot"])
    weights = fw["predict"] if isinstance(fw, dict) else fw
    return sorted(indices, key=lambda i: abs(float(weights[i])))


def _sorted_features_for_plotspec_alternative(params: dict) -> list[int]:
    """Return features_to_plot sorted ascending by ensured score (rnk_weight=0.5).

    PlotSpec renders in this order then inverts, so the highest-score alternative
    ends up at the top — matching Plotly's _rank_items(rnk_metric='ensured') output.
    """
    fw = params["feature_weights"]
    indices = list(params["features_to_plot"])
    if isinstance(fw, dict):
        predicts = fw["predict"]
        lows = fw.get("low", predicts)
        highs = fw.get("high", predicts)
    else:
        predicts = lows = highs = fw

    def _score(i: int) -> float:
        p = float(predicts[i])
        lo = float(lows[i])
        hi = float(highs[i])
        return 0.5 * p + 0.5 * (hi - lo)

    return sorted(indices, key=_score)


# ---------------------------------------------------------------------------
# Plotly render → HTML (and optionally PNG via kaleido)
# ---------------------------------------------------------------------------

def _render_plotly_html(
    explanation,
    style_id: str,
    *,
    task: str,
    output_path: Path,
    show_uncertainty: bool = False,
) -> None:
    plugin = _registry.find_plot_plugin(style_id)
    if plugin is None:
        print(f"  [skip] Plugin '{style_id}' not found in registry.")
        return

    intent_type = "alternative" if "alternative" in style_id else "factual"
    opts: dict = {"show_prediction_header": True}
    if show_uncertainty:
        opts["show_uncertainty"] = True
    context = PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=style_id,
        intent=MappingProxyType({"type": intent_type}),
        show=False,
        path=None,
        save_ext=None,
        options=MappingProxyType(opts),
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        artifact = plugin.build(context)
        result = plugin.render(artifact, context=context)

    fig = result.figure if hasattr(result, "figure") else result.extras.get("figure")
    if fig is None:
        print(f"  [skip] No figure returned for {style_id}.")
        return

    html_path = output_path.with_suffix(".html")
    fig.write_html(str(html_path))
    print(f"  Saved: {html_path.name}")

    try:
        png_path = output_path.with_suffix(".png")
        fig.write_image(str(png_path), width=900, height=500)
        print(f"  Saved: {png_path.name}")
    except Exception as exc:
        print(f"  [kaleido] PNG skipped: {exc}")


# ---------------------------------------------------------------------------
# Case definitions
# ---------------------------------------------------------------------------

def _run_cases(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-rank features so PlotSpec and Plotly display rows in the same order.
    # PlotSpec renders items top→bottom in features_to_plot order then inverts the
    # y-axis, making the LAST item the TOP row.  Plotly ranks descending and puts
    # the FIRST item at the top (autorange="reversed").  Sorting ascending before
    # calling PlotSpec makes both show the highest-ranked feature/alternative at top.
    _fprob_ranked   = _sorted_features_for_plotspec_factual(_FACTUAL_PROB)
    _freg_ranked    = _sorted_features_for_plotspec_factual(_FACTUAL_REG)
    _fmulti_ranked  = _sorted_features_for_plotspec_factual(_FACTUAL_MULTICLASS)
    _aprob_ranked   = _sorted_features_for_plotspec_alternative(_ALT_PROB)
    _areg_ranked    = _sorted_features_for_plotspec_alternative(_ALT_REG)
    _amulti_ranked  = _sorted_features_for_plotspec_alternative(_ALT_MULTICLASS)

    _multi_pos = f"P(Y={_FACTUAL_MULTICLASS['class_names'][_FACTUAL_MULTICLASS['predicted_class']]})"
    _multi_neg = f"P(Y!={_FACTUAL_MULTICLASS['class_names'][_FACTUAL_MULTICLASS['predicted_class']]})"

    cases = [
        # (name, plotspec_builder_fn, plotspec_kwargs, fake_expl_fn, style_id, task, show_uncertainty)
        (
            "factual_probabilistic",
            build_probabilistic_bars_spec,
            {
                "title": "factual_prob",
                "predict": _FACTUAL_PROB["predict"],
                "feature_weights": _FACTUAL_PROB["feature_weights"],
                "features_to_plot": _fprob_ranked,
                "column_names": _FACTUAL_PROB["column_names"],
                "instance": _FACTUAL_PROB["instance"],
                "y_minmax": _FACTUAL_PROB["y_minmax"],
                "interval": _FACTUAL_PROB["interval"],
                "neg_caption": _FACTUAL_PROB["neg_caption"],
                "pos_caption": _FACTUAL_PROB["pos_caption"],
            },
            lambda: _factual_fake_explanation(_FACTUAL_PROB, task="classification"),
            _FACTUAL_STYLE,
            "classification",
            _FACTUAL_PROB["interval"],
        ),
        (
            "factual_regression",
            build_regression_bars_spec,
            {
                "title": "factual_reg",
                "predict": _FACTUAL_REG["predict"],
                "feature_weights": _FACTUAL_REG["feature_weights"],
                "features_to_plot": _freg_ranked,
                "column_names": _FACTUAL_REG["column_names"],
                "instance": _FACTUAL_REG["instance"],
                "y_minmax": _FACTUAL_REG["y_minmax"],
                "interval": _FACTUAL_REG["interval"],
            },
            lambda: _factual_fake_explanation(_FACTUAL_REG, task="regression"),
            _FACTUAL_STYLE,
            "regression",
            _FACTUAL_REG["interval"],
        ),
        (
            "alternative_probabilistic",
            build_alternative_probabilistic_spec,
            {
                "title": "alt_prob",
                "predict": _ALT_PROB["predict"],
                "feature_weights": _ALT_PROB["feature_weights"],
                "features_to_plot": _aprob_ranked,
                "column_names": _ALT_PROB["column_names"],
                "instance": _ALT_PROB["instance"],
                "y_minmax": _ALT_PROB["y_minmax"],
                "interval": _ALT_PROB["interval"],
            },
            lambda: _alternative_fake_explanation(_ALT_PROB, task="classification"),
            _ALT_STYLE,
            "classification",
            False,
        ),
        (
            "alternative_regression",
            build_alternative_regression_spec,
            {
                "title": "alt_reg",
                "predict": _ALT_REG["predict"],
                "feature_weights": _ALT_REG["feature_weights"],
                "features_to_plot": _areg_ranked,
                "column_names": _ALT_REG["column_names"],
                "instance": _ALT_REG["instance"],
                "y_minmax": _ALT_REG["y_minmax"],
                "interval": _ALT_REG["interval"],
            },
            lambda: _alternative_fake_explanation(_ALT_REG, task="regression"),
            _ALT_STYLE,
            "regression",
            False,
        ),
        (
            "factual_multiclass",
            build_probabilistic_bars_spec,
            {
                "title": "factual_multiclass",
                "predict": _FACTUAL_MULTICLASS["predict"],
                "feature_weights": _FACTUAL_MULTICLASS["feature_weights"],
                "features_to_plot": _fmulti_ranked,
                "column_names": _FACTUAL_MULTICLASS["column_names"],
                "instance": _FACTUAL_MULTICLASS["instance"],
                "y_minmax": _FACTUAL_MULTICLASS["y_minmax"],
                "interval": _FACTUAL_MULTICLASS["interval"],
                "pos_caption": _multi_pos,
                "neg_caption": _multi_neg,
            },
            lambda: _factual_fake_explanation(_FACTUAL_MULTICLASS, task="classification"),
            _FACTUAL_STYLE,
            "classification",
            _FACTUAL_MULTICLASS["interval"],
        ),
        (
            "alternative_multiclass",
            build_alternative_probabilistic_spec,
            {
                "title": "alt_multiclass",
                "predict": _ALT_MULTICLASS["predict"],
                "feature_weights": _ALT_MULTICLASS["feature_weights"],
                "features_to_plot": _amulti_ranked,
                "column_names": _ALT_MULTICLASS["column_names"],
                "instance": _ALT_MULTICLASS["instance"],
                "y_minmax": _ALT_MULTICLASS["y_minmax"],
                "interval": _ALT_MULTICLASS["interval"],
            },
            lambda: _alternative_fake_explanation(_ALT_MULTICLASS, task="classification"),
            _ALT_STYLE,
            "classification",
            False,
        ),
    ]

    for name, spec_fn, spec_kwargs, expl_fn, style_id, task, show_uncertainty in cases:
        print(f"\n-- {name} --")

        # 1. PlotSpec → matplotlib PNG
        spec = spec_fn(**spec_kwargs)
        plotspec_png = output_dir / f"{name}_plotspec.png"
        try:
            _render_plotspec_png(spec, plotspec_png)
            print(f"  Saved: {plotspec_png.name}")
        except Exception as exc:
            print(f"  [matplotlib] error: {exc}")

        # 2. Plotly → HTML (+ optional kaleido PNG)
        explanation = expl_fn()
        plotly_out = output_dir / f"{name}_plotly"
        try:
            _render_plotly_html(
                explanation,
                style_id,
                task=task,
                output_path=plotly_out,
                show_uncertainty=show_uncertainty,
            )
        except Exception as exc:
            print(f"  [plotly] error: {exc}")

    _write_readme(output_dir)
    print(f"\nDone. Output: {output_dir}")


def _write_readme(output_dir: Path) -> None:
    readme = output_dir / "README.md"
    readme.write_text(
        "# PlotSpec vs Plotly — *_bars side-by-side artifacts\n\n"
        "Generated by `scripts/plot_parity/generate_side_by_side.py`.\n\n"
        "## Case pairs\n\n"
        "| Case | PlotSpec (matplotlib) | Plotly |\n"
        "|---|---|---|\n"
        "| factual_probabilistic | factual_probabilistic_plotspec.png | factual_probabilistic_plotly.html |\n"
        "| factual_regression | factual_regression_plotspec.png | factual_regression_plotly.html |\n"
        "| factual_multiclass | factual_multiclass_plotspec.png | factual_multiclass_plotly.html |\n"
        "| alternative_probabilistic | alternative_probabilistic_plotspec.png | alternative_probabilistic_plotly.html |\n"
        "| alternative_regression | alternative_regression_plotspec.png | alternative_regression_plotly.html |\n"
        "| alternative_multiclass | alternative_multiclass_plotspec.png | alternative_multiclass_plotly.html |\n\n"
        "## Review criteria\n\n"
        "- Row order and labels match\n"
        "- Bar colors match (hex)\n"
        "- Bar width identical (0.4)\n"
        "- X-axis range matches\n"
        "- Instance values appear on right-side axis\n"
        "- Uncertainty overlay renders on top of solid bar\n"
        "- Interval colors match for crossing-0.5 segments\n\n"
        "## Permitted Plotly-only differences\n\n"
        "- Hover cards on every bar\n"
        "- Interactive zoom/pan\n"
        "- HTML format instead of PNG\n",
        encoding="utf-8",
    )
    print(f"  Saved: {readme.name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate PlotSpec vs Plotly side-by-side reports for *_bars parity."
    )
    parser.add_argument(
        "--output-dir",
        default=str(_REPO_ROOT / "reports" / "plot_parity" / "plotspec_vs_plotly_bars"),
        help="Directory to write output files (default: reports/plot_parity/plotspec_vs_plotly_bars/)",
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Optional subdirectory tag (e.g. v0.2.1_fixes) to version the output.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if args.tag:
        output_dir = output_dir / args.tag

    _run_cases(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
