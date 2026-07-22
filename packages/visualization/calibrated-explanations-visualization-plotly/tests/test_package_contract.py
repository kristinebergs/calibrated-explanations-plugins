"""Package-level contract tests: entry points, registration, safety, escaping.

These tests back the maturity gates: declared entry points load and agree with
runtime registration, registration is idempotent, the deprecated style alias
resolves to the canonical builder/renderer, importing the package has no side
effects, missing backends fail actionably, and user-controlled labels are not
interpolated into executable HTML.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import calibrated_explanations.plugins.registry as registry
import pytest
from calibrated_explanations.plugins.plots import PlotRenderContext

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _PACKAGE_DIR / "src"

BOOTSTRAP_ID = "official.visualization.plotly.bootstrap"

_STYLE_IDS = (
    "plotly.local.uncertainty_quadrant",
    "plotly.local.ensured",
    "plotly.local.factual_bars",
    "plotly.local.factual_simple",
    "plotly.local.alternative_bars",
    "plotly.local.alternative_feature_summary",
    "plotly.global.instance_explorer",
    "plotly.dashboard.instance_workspace",
)
_ALIAS_STYLE_ID = "plotly.local.ensured_triangular"
_CANONICAL_FOR_ALIAS = "plotly.local.ensured"


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    # CE 1.0.0 removed clear_env_trust_cache() without a replacement, and the
    # process-level ConfigManager singleton snapshots os.environ once and
    # never re-reads it, so a monkeypatched CE_TRUST_PLUGIN has no effect
    # unless both the singleton and the registry's own env-trust cache are
    # reset (see development/oss_ce_upstream_log.md).
    from calibrated_explanations.core.config_manager import (
        reset_process_config_manager_for_testing,
    )

    reset_process_config_manager_for_testing()
    registry._ENV_TRUST_CACHE = None
    registry._PYPROJECT_TRUST_CACHE = None


def _load_plugin(monkeypatch):
    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        "ce_visualization_plotly.plugin:PlotlyVisualizationBootstrap," + BOOTSTRAP_ID,
    )
    module = importlib.import_module("ce_visualization_plotly.plugin")
    _reset_registry_state()
    module.register_plotly_visualization_components()
    return module


def _pyproject() -> dict:
    with (_PACKAGE_DIR / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _load_entry_point_target(target: str):
    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


# ---------------------------------------------------------------------------
# Entry points and metadata
# ---------------------------------------------------------------------------


def test_declared_entry_points_load_and_cover_all_styles(monkeypatch):
    data = _pyproject()
    entry_points = data["project"]["entry-points"]

    bootstrap_targets = entry_points["calibrated_explanations.plugins"]
    assert list(bootstrap_targets) == ["plotly_visualization"]
    bootstrap = _load_entry_point_target(bootstrap_targets["plotly_visualization"])
    assert bootstrap.plugin_meta["name"] == BOOTSTRAP_ID

    builders = entry_points["calibrated_explanations.plugins.plot_builders"]
    renderers = entry_points["calibrated_explanations.plugins.plot_renderers"]
    assert set(builders) == set(renderers), (
        "builder and renderer entry-point names must agree"
    )

    loaded_styles = set()
    for mapping, expected_capability in ((builders, "build"), (renderers, "render")):
        for target in mapping.values():
            loaded = _load_entry_point_target(target)
            assert hasattr(loaded, expected_capability), target
            meta = getattr(loaded, "plugin_meta", None)
            assert isinstance(meta, dict) and meta.get("name"), target
            style = meta.get("style")
            if style:
                loaded_styles.add(style)

    # Every runtime-registered style has a declared builder+renderer entry point.
    module = _load_plugin(monkeypatch)
    del module
    for style_id in _STYLE_IDS:
        descriptor = registry.find_plot_style_descriptor(style_id)
        assert descriptor is not None, f"{style_id} must be registered"


def test_bootstrap_plugin_meta_version_matches_package_version(monkeypatch):
    data = _pyproject()
    plugin = importlib.import_module("ce_visualization_plotly.plugin")
    assert (
        plugin.PlotlyVisualizationBootstrap.plugin_meta["version"]
        == data["project"]["version"]
    )


# ---------------------------------------------------------------------------
# Registration behaviour
# ---------------------------------------------------------------------------


def test_registration_is_idempotent(monkeypatch):
    module = _load_plugin(monkeypatch)
    before = {
        style_id: registry.find_plot_style_descriptor(style_id) for style_id in _STYLE_IDS
    }
    module.register_plotly_visualization_components()
    module.register_plotly_visualization_components()
    for style_id, descriptor in before.items():
        assert registry.find_plot_style_descriptor(style_id) is descriptor, (
            f"duplicate registration must not replace descriptor for {style_id}"
        )


def test_deprecated_alias_resolves_to_canonical_builder_and_renderer(monkeypatch):
    _load_plugin(monkeypatch)
    canonical = registry.find_plot_style_descriptor(_CANONICAL_FOR_ALIAS)
    alias = registry.find_plot_style_descriptor(_ALIAS_STYLE_ID)
    assert canonical is not None and alias is not None

    def _meta(descriptor):
        metadata = getattr(descriptor, "metadata", descriptor)
        return {
            "builder_id": metadata.get("builder_id"),
            "renderer_id": metadata.get("renderer_id"),
        }

    assert _meta(alias) == _meta(canonical)


# ---------------------------------------------------------------------------
# Import safety
# ---------------------------------------------------------------------------


def test_import_has_no_filesystem_or_network_side_effects(tmp_path):
    script = (
        "import socket\n"
        "class _GuardSocket(socket.socket):\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        raise AssertionError('network access during import')\n"
        "socket.socket = _GuardSocket\n"
        "def _blocked(*args, **kwargs):\n"
        "    raise AssertionError('network access during import')\n"
        "socket.create_connection = _blocked\n"
        "import ce_visualization_plotly.plugin\n"
        "print('IMPORT_OK')\n"
    )
    # Import the same code the suite under test imports: the installed
    # distribution when it matches pyproject, the source tree otherwise.
    from conftest import SRC_FALLBACK_ACTIVE

    env = dict(__import__("os").environ)
    if SRC_FALLBACK_ACTIVE:
        env["PYTHONPATH"] = str(_SRC_DIR)
    else:
        env.pop("PYTHONPATH", None)
    result = subprocess.run(  # noqa: S603 — fixed script, trusted interpreter
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
    leftover = [p for p in tmp_path.iterdir() if p.name != "__pycache__"]
    assert leftover == [], f"import must not write files: {leftover}"


# ---------------------------------------------------------------------------
# Missing backend behaviour
# ---------------------------------------------------------------------------


def _factual_fake_explanation():
    rules = {
        "weight": [0.4, -0.2],
        "weight_low": [0.3, -0.3],
        "weight_high": [0.5, -0.1],
        "rule": ["f0 > 1", "f1 <= 0"],
        "feature": [0, 1],
        "value": [1.5, -0.5],
        "feature_value": [1.5, -0.5],
    }
    collection = SimpleNamespace(feature_names=["f0", "f1"], y_minmax=[0.0, 1.0])
    local = SimpleNamespace(
        index=0,
        calibrated_explanations=collection,
        prediction={"predict": 0.7, "low": 0.6, "high": 0.8, "classes": 1},
        rules=rules,
        get_mode=lambda: "classification",
        is_regression=lambda: False,
        is_probabilistic=lambda: True,
        is_alternative=lambda: False,
    )
    collection.explanations = [local]
    collection.batch_metadata = {"task": "classification", "mode": "classification"}
    return collection


def _context(explanation, *, style, path=None, show=False, **options) -> PlotRenderContext:
    return PlotRenderContext(
        explanation=explanation,
        instance_metadata=MappingProxyType({"type": "instance"}),
        style=style,
        intent=MappingProxyType({"type": "factual"}),
        show=show,
        path=path,
        save_ext=None,
        options=MappingProxyType(options),
    )


def test_missing_plotly_produces_actionable_error(monkeypatch):
    factual_bars = importlib.import_module("ce_visualization_plotly.factual_bars")

    def _raise_import_error(*args, **kwargs):
        raise ImportError("No module named 'plotly'")

    monkeypatch.setattr(factual_bars, "build_figure", _raise_import_error)
    renderer = factual_bars.LocalFactualBarsPlotRenderer()
    builder = factual_bars.LocalFactualBarsPlotBuilder()
    context = _context(_factual_fake_explanation(), style=factual_bars.STYLE_ID)
    artifact = builder.build(context)
    with pytest.raises(RuntimeError, match="[Pp]lotly is required"):
        renderer.render(artifact, context=context)


# ---------------------------------------------------------------------------
# Output handling and escaping
# ---------------------------------------------------------------------------

_MALICIOUS_LABEL = "<script>alert('xss')</script>"


def _malicious_fake_explanation():
    collection = _factual_fake_explanation()
    local = collection.explanations[0]
    local.rules = {
        **local.rules,
        "rule": [_MALICIOUS_LABEL, "f1 <= 0 & \"quoted\" 'label'"],
    }
    collection.feature_names = [_MALICIOUS_LABEL, "unicode åäö × λ " + "long" * 100]
    return collection


def test_html_export_escapes_user_controlled_labels(monkeypatch, tmp_path):
    pytest.importorskip("plotly")
    factual_bars = importlib.import_module("ce_visualization_plotly.factual_bars")

    builder = factual_bars.LocalFactualBarsPlotBuilder()
    renderer = factual_bars.LocalFactualBarsPlotRenderer()
    out = tmp_path / "report.html"
    context = _context(
        _malicious_fake_explanation(),
        style=factual_bars.STYLE_ID,
        path=str(out),
        show_uncertainty=True,
    )
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)
    assert result.saved_paths == (str(out),)
    content = out.read_text(encoding="utf-8")
    assert "<script>alert(" not in content, (
        "user-controlled labels must not appear as executable HTML"
    )


def test_ensured_detail_markup_escapes_labels_and_values(monkeypatch):
    ensured = importlib.import_module("ce_visualization_plotly.ensured")
    markup = ensured._detail_markup(_MALICIOUS_LABEL, _MALICIOUS_LABEL)
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_unicode_and_long_labels_render(monkeypatch):
    pytest.importorskip("plotly")
    factual_bars = importlib.import_module("ce_visualization_plotly.factual_bars")

    collection = _factual_fake_explanation()
    local = collection.explanations[0]
    local.rules = {
        **local.rules,
        "rule": ["ålder ≤ 40 × λ 日本語", "x" * 400],
    }
    builder = factual_bars.LocalFactualBarsPlotBuilder()
    renderer = factual_bars.LocalFactualBarsPlotRenderer()
    context = _context(collection, style=factual_bars.STYLE_ID)
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)
    assert result.figure is not None


def test_output_path_suffix_coerced_to_html_and_overwrites(monkeypatch, tmp_path):
    pytest.importorskip("plotly")
    factual_bars = importlib.import_module("ce_visualization_plotly.factual_bars")

    builder = factual_bars.LocalFactualBarsPlotBuilder()
    renderer = factual_bars.LocalFactualBarsPlotRenderer()
    target = tmp_path / "figure.png"
    expected = tmp_path / "figure.html"
    expected.write_text("sentinel", encoding="utf-8")

    context = _context(
        _factual_fake_explanation(), style=factual_bars.STYLE_ID, path=str(target)
    )
    artifact = builder.build(context)
    result = renderer.render(artifact, context=context)

    assert result.saved_paths == (str(expected),)
    assert not target.exists(), "non-HTML suffix must be coerced, not written"
    content = expected.read_text(encoding="utf-8")
    assert content != "sentinel", "documented behaviour: target path is overwritten"


# ---------------------------------------------------------------------------
# CE public metadata contract
# ---------------------------------------------------------------------------


def test_every_component_passes_ce_public_metadata_validators():
    """Each entry-point component passes CE's public ADR-006/ADR-014 validators,
    reports the distribution version, the monorepo provider identity, and the
    capability tag matching its role (vocabulary from CE builtins)."""
    from calibrated_explanations.plugins import validate_plugin_meta
    from calibrated_explanations.plugins.registry import (
        validate_plot_builder_metadata,
        validate_plot_renderer_metadata,
    )

    data = _pyproject()
    version = data["project"]["version"]
    entry_points = data["project"]["entry-points"]

    for group, role_validator, expected_capability in (
        (
            "calibrated_explanations.plugins.plot_builders",
            validate_plot_builder_metadata,
            "plot:builder",
        ),
        (
            "calibrated_explanations.plugins.plot_renderers",
            validate_plot_renderer_metadata,
            "plot:renderer",
        ),
    ):
        for name, target in entry_points[group].items():
            component = _load_entry_point_target(target)
            meta = dict(component.plugin_meta)
            validate_plugin_meta(meta)
            role_validator(dict(component.plugin_meta))
            assert meta["version"] == version, (name, meta["version"])
            assert meta["provider"] == "calibrated-explanations-plugins", name
            assert list(meta["capabilities"]) == [expected_capability], (
                name,
                meta["capabilities"],
            )

    bootstrap = _load_entry_point_target(
        entry_points["calibrated_explanations.plugins"]["plotly_visualization"]
    )
    meta = dict(bootstrap.plugin_meta)
    validate_plugin_meta(meta)
    assert meta["version"] == version
    assert meta["provider"] == "calibrated-explanations-plugins"
    assert set(meta["capabilities"]) == {"plot:builder", "plot:renderer"}


def test_artifact_schema_versions_are_declared_separately():
    """Every style module keeps an ARTIFACT_VERSION (payload schema version)
    distinct from plugin_meta['version'] (the distribution version)."""
    for module_name in (
        "alternative_bars",
        "alternative_feature_summary",
        "ensured",
        "factual_bars",
        "factual_simple",
        "instance_explorer",
        "instance_workspace",
        "quadrant",
    ):
        module = importlib.import_module(f"ce_visualization_plotly.{module_name}")
        artifact_version = getattr(module, "ARTIFACT_VERSION", None)
        assert isinstance(artifact_version, str) and artifact_version, module_name


def test_root_import_registers_nothing_and_patches_nothing():
    """Importing the package must not register plot styles or replace any CE
    plotting callable; registration is always an explicit call."""
    script = (
        "import calibrated_explanations.plotting as ce_plotting\n"
        "from calibrated_explanations.explanations import (\n"
        "    AlternativeExplanation, FactualExplanation)\n"
        "import calibrated_explanations.plugins.registry as registry\n"
        "original_plot_global = ce_plotting.plot_global\n"
        "original_factual_plot = FactualExplanation.plot\n"
        "original_alternative_plot = AlternativeExplanation.plot\n"
        "import ce_visualization_plotly  # noqa: F401\n"
        "import ce_visualization_plotly.plugin  # noqa: F401\n"
        "assert ce_plotting.plot_global is original_plot_global, (\n"
        "    'import must not replace plot_global')\n"
        "assert FactualExplanation.plot is original_factual_plot, (\n"
        "    'import must not replace FactualExplanation.plot')\n"
        "assert AlternativeExplanation.plot is original_alternative_plot, (\n"
        "    'import must not replace AlternativeExplanation.plot')\n"
        "assert registry.find_plot_style_descriptor('plotly.local.factual_bars') is None, (\n"
        "    'import must not register styles')\n"
        "print('NO_SIDE_EFFECTS')\n"
    )
    from conftest import SRC_FALLBACK_ACTIVE

    env = dict(__import__("os").environ)
    if SRC_FALLBACK_ACTIVE:
        env["PYTHONPATH"] = str(_SRC_DIR)
    else:
        env.pop("PYTHONPATH", None)
    result = subprocess.run(  # noqa: S603 — fixed script, trusted interpreter
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "NO_SIDE_EFFECTS" in result.stdout


def test_registration_never_replaces_ce_plotting_callables(monkeypatch):
    """CE >=1.0.0rc2 native dispatch requires no bridge: registering (and
    re-registering) the Plotly components must never touch
    ``FactualExplanation.plot``."""
    from calibrated_explanations.explanations import FactualExplanation

    module = _load_plugin(monkeypatch)
    original = FactualExplanation.plot

    module.register_plotly_visualization_components()
    assert FactualExplanation.plot is original, "registration must not replace CE callables"

    module.register_plotly_visualization_components()
    assert FactualExplanation.plot is original, (
        "repeated registration must not replace CE callables"
    )
