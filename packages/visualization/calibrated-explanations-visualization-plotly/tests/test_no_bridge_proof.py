"""RC2 no-bridge proof: symbol-integrity and dispatch-fidelity evidence.

This module is the promotion-audit evidence that this plugin dispatches
natively through CE >=1.0.0rc2's public plot-plugin contract, with no
compatibility bridge, monkey-patch, or wrapper of any CE plotting callable.

Unlike most of this package's other test modules (which build ``PlotArtifact``
directly from a fake ``PlotRenderContext``), every dispatch test here goes
through CE's actual public user-facing APIs (``CalibratedExplainer``,
explanation/collection ``.plot(...)``, ``explainer.plot(...)``) so that a
regression in CE's own dispatch machinery, not just this plugin's builders,
would be caught here too.
"""

from __future__ import annotations

import importlib
import zipfile
from pathlib import Path

import calibrated_explanations.plotting as ce_plotting
import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations import CalibratedExplainer, WrapCalibratedExplainer
from calibrated_explanations.explanations import AlternativeExplanation, FactualExplanation
from calibrated_explanations.utils.exceptions import ConfigurationError
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"

_ALL_STYLE_IDS = (
    "plotly.local.factual_bars",
    "plotly.local.factual_simple",
    "plotly.local.alternative_bars",
    "plotly.local.ensured",
    "plotly.local.alternative_feature_summary",
    "plotly.local.uncertainty_quadrant",
    "plotly.global.instance_explorer",
    "plotly.dashboard.instance_workspace",
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()


@pytest.fixture
def classifier_explainer():
    """A small, real, fitted+calibrated CE explainer -- no fakes."""
    features, labels = make_classification(
        n_samples=160,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.3, random_state=0, stratify=labels
    )
    model = LogisticRegression(random_state=0, solver="liblinear").fit(x_train, y_train)
    explainer = CalibratedExplainer(model, x_train, y_train, mode="classification", seed=0)
    return explainer, x_test, y_test


class _CallableSnapshot:
    """Captures identity of every CE plotting callable this plugin must never touch."""

    def __init__(self) -> None:
        self.factual_plot = FactualExplanation.plot
        self.alternative_plot = AlternativeExplanation.plot
        self.explainer_plot = CalibratedExplainer.plot
        self.wrap_plot = WrapCalibratedExplainer.plot
        self.plot_global = ce_plotting.plot_global

    def assert_unchanged(self, label: str) -> None:
        assert FactualExplanation.plot is self.factual_plot, (
            f"{label}: FactualExplanation.plot identity changed"
        )
        assert AlternativeExplanation.plot is self.alternative_plot, (
            f"{label}: AlternativeExplanation.plot identity changed"
        )
        assert CalibratedExplainer.plot is self.explainer_plot, (
            f"{label}: CalibratedExplainer.plot identity changed"
        )
        assert WrapCalibratedExplainer.plot is self.wrap_plot, (
            f"{label}: WrapCalibratedExplainer.plot identity changed"
        )
        assert ce_plotting.plot_global is self.plot_global, (
            f"{label}: plotting.plot_global identity changed"
        )


# ---------------------------------------------------------------------------
# _ce_compat absence
# ---------------------------------------------------------------------------


def test_ce_compat_module_is_absent_from_source():
    """The obsolete compatibility module must not exist anywhere in src/."""
    matches = list((_PACKAGE_DIR / "src").rglob("_ce_compat.py"))
    assert matches == [], f"obsolete _ce_compat.py present at: {matches}"

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ce_visualization_plotly._ce_compat")


def test_ce_compat_module_is_absent_from_built_wheel():
    """The built wheel artifact must not contain the obsolete bridge module."""
    pytest.importorskip("build")
    import subprocess
    import sys
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ce-no-bridge-wheel-") as tmp:
        subprocess.check_call(  # noqa: S603 -- fixed args, trusted interpreter
            [sys.executable, "-m", "build", "--wheel", "--outdir", tmp, str(_PACKAGE_DIR)],
        )
        wheels = list(Path(tmp).glob("*.whl"))
        assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"
        with zipfile.ZipFile(wheels[0]) as archive:
            names = archive.namelist()
        offenders = [name for name in names if "_ce_compat" in name]
        assert offenders == [], f"built wheel contains bridge artifacts: {offenders}"


# ---------------------------------------------------------------------------
# Symbol-integrity proof
# ---------------------------------------------------------------------------


def test_symbol_identity_unchanged_through_full_plugin_lifecycle(
    monkeypatch, classifier_explainer, tmp_path
):
    """CE plotting callables must keep their original identity across every
    lifecycle checkpoint: package import, plugin-module import, entry-point
    discovery, first registration, repeated registration, and rendering
    every one of the eight styles."""
    snapshot = _CallableSnapshot()
    snapshot.assert_unchanged("before any import")

    import ce_visualization_plotly  # noqa: F401

    snapshot.assert_unchanged("after package import")

    import ce_visualization_plotly.plugin as plotly_plugin

    snapshot.assert_unchanged("after plugin-module import")

    from importlib.metadata import entry_points

    discovered = entry_points(group="calibrated_explanations.plugins")
    bootstrap_entries = [
        ep for ep in discovered if ep.value.endswith(":PlotlyVisualizationBootstrap")
    ]
    if bootstrap_entries:
        bootstrap_entries[0].load()
    snapshot.assert_unchanged("after entry-point discovery")

    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap," + BOOTSTRAP_ID,
    )
    _reset_registry_state()

    plotly_plugin.register_plotly_visualization_components()
    snapshot.assert_unchanged("after first registration")

    plotly_plugin.register_plotly_visualization_components()
    snapshot.assert_unchanged("after repeated registration")

    explainer, x_test, y_test = classifier_explainer

    factuals = explainer.explain_factual(x_test[:2])
    alternatives = explainer.explore_alternatives(x_test[:2])

    factuals[0].plot(style="plotly.local.factual_bars", show=False)
    snapshot.assert_unchanged("after rendering factual_bars")
    factuals[0].plot(style="plotly.local.factual_simple", show=False)
    snapshot.assert_unchanged("after rendering factual_simple")
    factuals[0].plot(style="plotly.local.uncertainty_quadrant", show=False)
    snapshot.assert_unchanged("after rendering uncertainty_quadrant")
    alternatives[0].plot(style="plotly.local.alternative_bars", show=False)
    snapshot.assert_unchanged("after rendering alternative_bars")
    alternatives[0].plot(style="plotly.local.alternative_feature_summary", show=False)
    snapshot.assert_unchanged("after rendering alternative_feature_summary")
    alternatives.plot(style="plotly.local.ensured", show=False)
    snapshot.assert_unchanged("after rendering ensured")
    explainer.plot(x_test[:5], y_test[:5], style="plotly.global.instance_explorer", show=False)
    snapshot.assert_unchanged("after rendering instance_explorer")
    explainer.plot(
        x_test[:5],
        y_test[:5],
        style="plotly.dashboard.instance_workspace",
        dashboard_mode="standalone_html",
        precompute="selected",
        selected_instance_indices=[0],
        path=str(tmp_path / "workspace.html"),
        show=False,
    )
    snapshot.assert_unchanged("after rendering instance_workspace")


# ---------------------------------------------------------------------------
# Dispatch-fidelity proof
# ---------------------------------------------------------------------------


def test_dispatch_single_factual_explanation_via_public_api(monkeypatch, classifier_explainer):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    factual = explainer.explain_factual(x_test[:1])[0]
    result = factual.plot(
        style="plotly.local.factual_bars",
        show=False,
        filter_top=3,
        uncertainty=True,
        rnk_metric="ensured",
        rnk_weight=0.25,
    )

    assert result.artifact["style"] == "plotly.local.factual_bars"
    used = result.artifact["options_used"]
    assert used["filter_top"] == 3
    assert used["show_uncertainty"] is True
    assert used["rnk_metric"] == "ensured"
    assert used["rnk_weight"] == 0.25
    assert len(result.artifact["items"]) <= 3
    assert result.figure is not None


def test_dispatch_factual_collection_via_public_api(monkeypatch, classifier_explainer):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    factuals = explainer.explain_factual(x_test[:3])
    result = factuals.plot(style="plotly.local.factual_bars", show=False, filter_top=2)

    assert result.artifact["style"] == "plotly.local.factual_bars"
    assert result.artifact["options_used"]["filter_top"] == 2
    assert result.figure is not None


def test_dispatch_single_alternative_explanation_via_public_api(monkeypatch, classifier_explainer):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    alternative = explainer.explore_alternatives(x_test[:1])[0]
    result = alternative.plot(
        style="plotly.local.alternative_bars",
        show=False,
        filter_top=4,
        rnk_metric="ensured",
        rnk_weight=0.5,
    )

    used = result.artifact["options_used"]
    assert used["filter_top"] == 4
    assert used["rnk_metric"] == "ensured"
    assert used["rnk_weight"] == 0.5
    assert result.figure is not None


def test_dispatch_alternative_collection_via_public_api(monkeypatch, classifier_explainer):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    alternatives = explainer.explore_alternatives(x_test[:2])
    result = alternatives.plot(style="plotly.local.alternative_bars", show=False, filter_top=2)

    assert result.artifact["options_used"]["filter_top"] == 2
    assert result.figure is not None


def test_dispatch_explainer_level_global_plotting_via_public_api(
    monkeypatch, classifier_explainer
):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, y_test = classifier_explainer

    result = explainer.plot(
        x_test[:12],
        y_test[:12],
        style="plotly.global.instance_explorer",
        task="classification",
        position_precision=2,
        include_instance_records=True,
        aggregate_positions=True,
        show=False,
    )

    assert result.artifact["style"] == "plotly.global.instance_explorer"
    assert len(result.artifact["instance_records"]) == 12
    assert result.figure is not None


def test_dispatch_standalone_dashboard_via_public_api(monkeypatch, classifier_explainer, tmp_path):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, y_test = classifier_explainer

    out = tmp_path / "workspace.html"
    result = explainer.plot(
        x_test[:8],
        y_test[:8],
        style="plotly.dashboard.instance_workspace",
        dashboard_mode="standalone_html",
        precompute="top_uncertain",
        max_precomputed_instances=3,
        available_cards="auto",
        path=str(out),
        show=False,
    )

    assert result.saved_paths == (str(out),)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_repeated_registration_preserves_dispatch_fidelity(monkeypatch, classifier_explainer):
    """Registering twice must not change dispatch behaviour or options."""
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    factual = explainer.explain_factual(x_test[:1])[0]
    result = factual.plot(style="plotly.local.factual_bars", show=False, filter_top=2)
    assert result.artifact["options_used"]["filter_top"] == 2


def test_builtin_style_after_plotly_registration_never_reaches_plotly_builder(
    monkeypatch, classifier_explainer
):
    """A built-in (non-Plotly) style must render through CE's own default
    path, never through this plugin's builder, even after Plotly styles have
    been registered."""
    _reset_registry_state()
    import ce_visualization_plotly.factual_bars as factual_bars_module
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()

    def _fail(*_args, **_kwargs):
        raise AssertionError("Plotly builder must not be invoked for a built-in style")

    monkeypatch.setattr(
        factual_bars_module.LocalFactualBarsPlotBuilder, "build", _fail, raising=True
    )

    explainer, x_test, _ = classifier_explainer
    factual = explainer.explain_factual(x_test[:1])[0]

    # CE's own built-in "regular" style renders via matplotlib, which is not
    # a runtime (or base-install test) dependency of this package -- it is
    # only pulled in by the test-only `calibrated-explanations[viz]` extra.
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    factual.plot(style="regular", show=False)  # must not raise


# ---------------------------------------------------------------------------
# Negative tests: typos and unsupported options must not disappear silently
# ---------------------------------------------------------------------------


def test_unknown_style_raises_actionable_configuration_error(monkeypatch, classifier_explainer):
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    with pytest.raises(ConfigurationError, match="plotly.nonexistent.style"):
        explainer.plot(x_test[:1], style="plotly.nonexistent.style", show=False)


def test_typoed_option_emits_governed_warning_not_silent_at_collection_level(
    monkeypatch, classifier_explainer
):
    """A typoed kwarg (``filter_tp`` for ``filter_top``) must not vanish
    silently: CE's collection-level dispatch (``CalibratedExplanations.plot``)
    emits a governed ``UserWarning`` naming the unrecognised key and the
    built-in arguments it might be confused with."""
    _reset_registry_state()
    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    factuals = explainer.explain_factual(x_test[:1])
    with pytest.warns(UserWarning, match="filter_tp"):
        factuals.plot(style="plotly.local.factual_bars", show=False, filter_tp=2)


def test_typoed_option_on_single_explanation_is_a_known_ce_gap(monkeypatch, classifier_explainer):
    """Documents a known CE-core gap (not fixable in this plugin): unlike the
    collection-level path, a single indexed explanation's ``.plot(...)``
    forwards an unrecognised kwarg with no warning at all. This is recorded
    here as an executable limitation, not silently assumed away -- see
    MATURITY.md "Known limitations"."""
    _reset_registry_state()
    import warnings

    import ce_visualization_plotly.plugin as plotly_plugin

    plotly_plugin.register_plotly_visualization_components()
    explainer, x_test, _ = classifier_explainer

    factual = explainer.explain_factual(x_test[:1])[0]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        factual.plot(style="plotly.local.factual_bars", show=False, filter_tp=2)
    assert caught == [], (
        "if this now warns, CE has closed the gap: tighten this test into a "
        "positive pytest.warns assertion and drop this xfail-style comment"
    )
