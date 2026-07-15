from __future__ import annotations

import argparse
import re
from pathlib import Path
from textwrap import dedent, indent

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAIN_ENTRYPOINT_GROUP = "calibrated_explanations.plugins"

DOCS_HOME = "https://calibrated-explanations.readthedocs.io/en/latest/"
PLUGIN_CONTRACT = (
    "https://calibrated-explanations.readthedocs.io/en/latest/contributor/plugin-contract.html"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a CE plugin or metapackage.")
    parser.add_argument("--family", required=True, choices=(*PLUGIN_FAMILIES, "meta"))
    parser.add_argument("--package-type", required=True, choices=("plugin", "meta"))
    parser.add_argument("--slug", required=True)
    parser.add_argument("--distribution-name", required=True)
    parser.add_argument("--ce-range", required=True)
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--provider", default="official")
    parser.add_argument("--import-name")
    parser.add_argument("--plugin-identifier")
    parser.add_argument("--entrypoint-group", default=MAIN_ENTRYPOINT_GROUP)
    parser.add_argument("--capability", action="append", dest="capabilities")
    parser.add_argument(
        "--status",
        default="experimental",
        choices=("experimental", "mature"),
        help=(
            "Lifecycle status of the new plugin. New plugins start experimental; "
            "mature status is granted through a maturity-review PR, not scaffolding."
        ),
    )
    args = parser.parse_args()

    if not SLUG_PATTERN.match(args.slug):
        raise SystemExit("--slug must use lowercase kebab-case")
    if args.status != "experimental":
        raise SystemExit(
            "Direct mature scaffolding is not supported. New plugins are scaffolded "
            'with status = "experimental" and promoted to mature through a '
            "maturity-review pull request (see docs/plugin-lifecycle.md)."
        )
    if args.family == "meta" and args.package_type != "meta":
        raise SystemExit("--family meta requires --package-type meta")
    if args.family != "meta" and args.package_type != "plugin":
        raise SystemExit("Plugin families require --package-type plugin")
    if args.entrypoint_group != MAIN_ENTRYPOINT_GROUP:
        raise SystemExit(
            f"--entrypoint-group must be {MAIN_ENTRYPOINT_GROUP!r} for official scaffolds"
        )

    package_dir = PACKAGES_DIR / args.family / args.distribution_name
    if package_dir.exists():
        raise SystemExit(f"Package already exists: {package_dir}")

    if args.package_type == "plugin":
        if not args.import_name or not args.plugin_identifier or not args.capabilities:
            raise SystemExit(
                "Plugin packages require --import-name, --plugin-identifier, and --capability"
            )
        write_plugin_package(
            package_dir=package_dir,
            family=args.family,
            slug=args.slug,
            distribution_name=args.distribution_name,
            import_name=args.import_name,
            plugin_identifier=args.plugin_identifier,
            entrypoint_group=args.entrypoint_group,
            capabilities=args.capabilities,
            ce_range=args.ce_range,
            version=args.version,
            provider=args.provider,
        )
    else:
        write_meta_package(
            package_dir=package_dir,
            distribution_name=args.distribution_name,
            ce_range=args.ce_range,
            version=args.version,
        )

    print(f"Created {args.package_type} package at {package_dir.relative_to(ROOT)}")
    return 0


def write_plugin_package(
    *,
    package_dir: Path,
    family: str,
    slug: str,
    distribution_name: str,
    import_name: str,
    plugin_identifier: str,
    entrypoint_group: str,
    capabilities: list[str],
    ce_range: str,
    version: str,
    provider: str,
) -> None:
    src_dir = package_dir / "src" / import_name
    tests_dir = package_dir / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    if family == "calibration":
        init_py, plugin_py, test_py, entry_point_block = build_calibration_files(
            slug=slug,
            import_name=import_name,
            plugin_identifier=plugin_identifier,
            capabilities=capabilities,
            version=version,
            provider=provider,
            entrypoint_group=entrypoint_group,
        )
    elif family == "explanation":
        init_py, plugin_py, test_py, entry_point_block = build_explanation_files(
            slug=slug,
            import_name=import_name,
            plugin_identifier=plugin_identifier,
            capabilities=capabilities,
            version=version,
            provider=provider,
            entrypoint_group=entrypoint_group,
        )
    else:
        init_py, plugin_py, test_py, entry_point_block = build_visualization_files(
            slug=slug,
            import_name=import_name,
            plugin_identifier=plugin_identifier,
            capabilities=capabilities,
            version=version,
            provider=provider,
        )

    pyproject = build_plugin_pyproject(
        distribution_name=distribution_name,
        family=family,
        import_name=import_name,
        entry_point_block=entry_point_block,
        ce_range=ce_range,
        version=version,
    )
    readme = build_plugin_readme(
        distribution_name=distribution_name,
        family=family,
        ce_range=ce_range,
    )

    (package_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (package_dir / "README.md").write_text(readme, encoding="utf-8")
    (src_dir / "__init__.py").write_text(init_py, encoding="utf-8")
    (src_dir / "plugin.py").write_text(plugin_py, encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / f"test_{slug.replace('-', '_')}.py").write_text(test_py, encoding="utf-8")


def build_plugin_pyproject(
    *,
    distribution_name: str,
    family: str,
    import_name: str,
    entry_point_block: str,
    ce_range: str,
    version: str,
) -> str:
    dependency_spec = (
        f"calibrated-explanations[viz]{ce_range}"
        if family == "visualization"
        else f"calibrated-explanations{ce_range}"
    )
    return dedent(
        f"""\
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "{distribution_name}"
        version = "{version}"
        description = "{family.capitalize()} plugin for calibrated-explanations"
        readme = "README.md"
        requires-python = ">=3.11"
        dependencies = [
            "{dependency_spec}",
        ]

        {entry_point_block}

        [tool.hatch.build.targets.wheel]
        packages = ["src/{import_name}"]

        [tool.ce_plugin_repo]
        family = "{family}"
        status = "experimental"
        import_name = "{import_name}"
        """
    )


def build_plugin_readme(*, distribution_name: str, family: str, ce_range: str) -> str:
    return dedent(
        f"""\
        # {distribution_name}

        Family: `{family}`

        Status: `experimental`

        > **Experimental**: this plugin has not completed a maturity review and is
        > not published to PyPI. Interfaces and behaviour may change without notice.

        Purpose: Scaffolded {family} plugin package aligned to the CE plugin contract.

        Install (from a checkout of this repository):

        ```bash
        pip install ./packages/{family}/{distribution_name}
        ```

        Compatibility: `calibrated-explanations{ce_range}`

        Known limitations:

        - Newly scaffolded; delegates to CE built-ins and has not been reviewed
          for maturity. Document real assumptions, limitations, and failure
          modes here as the implementation evolves.

        Upstream docs:

        - CE Read the Docs: <{DOCS_HOME}>
        - Plugin contract: <{PLUGIN_CONTRACT}>
        - Lifecycle policy: `docs/plugin-lifecycle.md` in this repository
        """
    )


def build_calibration_files(
    *,
    slug: str,
    import_name: str,
    plugin_identifier: str,
    capabilities: list[str],
    version: str,
    provider: str,
    entrypoint_group: str,
) -> tuple[str, str, str, str]:
    class_name = "".join(part.capitalize() for part in slug.split("-")) + "IntervalCalibratorPlugin"
    entry_name = slug.replace("-", "_")
    modes = infer_interval_modes(capabilities)
    init_py = dedent(
        f"""\
        \"\"\"Package for {import_name}.\"\"\"

        from .plugin import {class_name}

        __all__ = ["{class_name}"]
        """
    )
    plugin_py = dedent(
        f"""\
        from __future__ import annotations

        from typing import Any

        from calibrated_explanations.plugins.builtins import LegacyIntervalCalibratorPlugin
        from calibrated_explanations.plugins.intervals import (
            IntervalCalibratorContext,
            IntervalCalibratorPlugin,
        )
        from calibrated_explanations.plugins.registry import (
            find_interval_descriptor,
            register_interval_plugin,
        )


        class {class_name}(IntervalCalibratorPlugin):
            \"\"\"Delegating interval calibrator that stays runtime-valid by default.\"\"\"

            plugin_meta = {{
                "schema_version": 1,
                "name": "{plugin_identifier}",
                "version": "{version}",
                "provider": "{provider}",
                "data_modalities": ("tabular",),
                "capabilities": {capabilities},
                "modes": {modes},
                "dependencies": ("core.interval.legacy",),
                "trusted": False,
                "trust": False,
                "confidence_source": "legacy-delegate",
                "requires_bins": False,
                "fast_compatible": False,
                "config_schema": {{
                    "version": 1,
                    "additional_properties": False,
                    "keys": {{
                        "enabled": {{"type": "bool", "default": True}},
                    }},
                }},
            }}

            def __init__(self) -> None:
                self._delegate = LegacyIntervalCalibratorPlugin()

            def create(self, context: IntervalCalibratorContext, *, fast: bool = False) -> Any:
                return self._delegate.create(context, fast=fast)


        def register_scaffold_interval_plugin() -> None:
            if find_interval_descriptor("{plugin_identifier}") is not None:
                return
            register_interval_plugin("{plugin_identifier}", {class_name}(), source="entrypoint")


        register_scaffold_interval_plugin()
        """
    )
    test_py = dedent(
        f"""\
        import numpy as np
        import pytest

        pytest.importorskip("calibrated_explanations")

        from calibrated_explanations import CalibratedExplainer
        import calibrated_explanations.plugins.registry as registry
        from sklearn.datasets import make_classification
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split


        def _reset_registry_state() -> None:
            reset_catalog = getattr(registry, "reset_plugin_catalog", None)
            if callable(reset_catalog):
                reset_catalog(kind="all")
            clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
            if callable(clear_env_cache):
                clear_env_cache()
            clear_warnings = getattr(registry, "clear_trust_warnings", None)
            if callable(clear_warnings):
                clear_warnings()


        def test_plugin_should_be_runtime_consumable(monkeypatch):
            monkeypatch.setenv(
                "CE_TRUST_PLUGIN",
                ",".join(
                    [
                        "{plugin_identifier}",
                        "{import_name}.plugin:{class_name}",
                    ]
                ),
            )
            _reset_registry_state()
            registry.load_entrypoint_plugins(include_untrusted=False)

            descriptor = registry.find_interval_descriptor("{plugin_identifier}")
            assert descriptor is not None
            assert descriptor.trusted is True

            x, y = make_classification(
                n_samples=80,
                n_features=6,
                n_informative=4,
                n_redundant=0,
                random_state=0,
            )
            x_train, x_test, y_train, _ = train_test_split(
                x, y, test_size=0.2, random_state=0, stratify=y
            )
            learner = LogisticRegression(random_state=0, solver="liblinear")
            learner.fit(x_train, y_train)

            explainer = CalibratedExplainer(
                learner,
                x_train,
                y_train,
                mode="classification",
                seed=0,
                interval_plugin="{plugin_identifier}",
            )
            prediction = explainer.predict(x_test[:3], calibrated=True)
            assert np.asarray(prediction).shape == (3,)
            assert explainer.interval_plugin_identifiers["default"] == "{plugin_identifier}"
        """
    )
    entry_point_block = dedent(
        f"""\
        [project.entry-points."{entrypoint_group}"]
        {entry_name} = "{import_name}.plugin:{class_name}"
        """
    ).strip()
    return init_py, plugin_py, test_py, entry_point_block


def build_explanation_files(
    *,
    slug: str,
    import_name: str,
    plugin_identifier: str,
    capabilities: list[str],
    version: str,
    provider: str,
    entrypoint_group: str,
) -> tuple[str, str, str, str]:
    class_name = "".join(part.capitalize() for part in slug.split("-")) + "ExplanationPlugin"
    entry_name = slug.replace("-", "_")
    mode = infer_single_explanation_mode(capabilities)
    tasks = infer_explanation_tasks(capabilities)
    normalized_capabilities = normalize_explanation_capabilities(capabilities, mode, tasks)
    delegate_import_block, delegate_init_block = explanation_delegate(mode)
    delegate_init_code = indent(delegate_init_block, " " * 8)
    explain_method = explanation_api_method(mode)
    override_name = explanation_override_name(mode)
    entrypoint_target = f"{import_name}.plugin:{class_name}"
    init_py = dedent(
        f"""\
        \"\"\"Package for {import_name}.\"\"\"

        from .plugin import {class_name}

        __all__ = ["{class_name}"]
        """
    )
    plugin_py = dedent(
        f"""\
        from __future__ import annotations

        from typing import Any

        from calibrated_explanations.plugins.explanations import (
            ExplanationBatch,
            ExplanationContext,
            ExplanationPlugin,
            ExplanationRequest,
        )
        from calibrated_explanations.plugins.registry import (
            find_explanation_descriptor,
            register_explanation_plugin,
        )
        {delegate_import_block}


        class {class_name}(ExplanationPlugin):
            \"\"\"Delegating explanation plugin that mirrors CE runtime behavior.\"\"\"

            plugin_meta = {{
                "schema_version": 1,
                "name": "{plugin_identifier}",
                "version": "{version}",
                "provider": "{provider}",
                "data_modalities": ("tabular",),
                "capabilities": {normalized_capabilities},
                "modes": ("{mode}",),
                "tasks": {tasks},
                "dependencies": ("core.interval.legacy", "plot_spec.default"),
                "trusted": False,
                "trust": False,
                "config_schema": {{
                    "version": 1,
                    "additional_properties": False,
                    "keys": {{
                        "label_prefix": {{"type": "str", "default": ""}},
                        "enabled_labels": {{"type": "list[str]", "default": []}},
                    }},
                }},
            }}

            def __init__(self) -> None:
        __DELEGATE_INIT__

            def supports(self, model: Any) -> bool:
                return self._delegate.supports(model)

            def supports_mode(self, mode: str, *, task: str) -> bool:
                return self._delegate.supports_mode(mode, task=task)

            def initialize(self, context: ExplanationContext) -> None:
                self._delegate.initialize(context)

            def explain_batch(self, x: Any, request: ExplanationRequest) -> ExplanationBatch:
                return self._delegate.explain_batch(x, request)


        def register_scaffold_explanation_plugin() -> None:
            if find_explanation_descriptor("{plugin_identifier}") is not None:
                return
            register_explanation_plugin("{plugin_identifier}", {class_name}(), source="entrypoint")


        register_scaffold_explanation_plugin()
        """
    ).replace("__DELEGATE_INIT__", delegate_init_code)
    test_py = dedent(
        f"""\
        import pytest

        pytest.importorskip("calibrated_explanations")

        from calibrated_explanations import CalibratedExplainer
        import calibrated_explanations.plugins.registry as registry
        from sklearn.datasets import make_classification
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split


        def _reset_registry_state() -> None:
            reset_catalog = getattr(registry, "reset_plugin_catalog", None)
            if callable(reset_catalog):
                reset_catalog(kind="all")
            clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
            if callable(clear_env_cache):
                clear_env_cache()
            clear_warnings = getattr(registry, "clear_trust_warnings", None)
            if callable(clear_warnings):
                clear_warnings()


        def test_plugin_should_be_runtime_consumable(monkeypatch):
            monkeypatch.setenv(
                "CE_TRUST_PLUGIN",
                ",".join(
                    [
                        "{plugin_identifier}",
                        "{entrypoint_target}",
                    ]
                ),
            )
            _reset_registry_state()
            registry.load_entrypoint_plugins(include_untrusted=False)

            descriptor = registry.find_explanation_descriptor("{plugin_identifier}")
            assert descriptor is not None
            assert descriptor.trusted is True

            x, y = make_classification(
                n_samples=80,
                n_features=6,
                n_informative=4,
                n_redundant=0,
                random_state=0,
            )
            x_train, x_test, y_train, _ = train_test_split(
                x, y, test_size=0.2, random_state=0, stratify=y
            )
            learner = LogisticRegression(random_state=0, solver="liblinear")
            learner.fit(x_train, y_train)

            explainer = CalibratedExplainer(
                learner,
                x_train,
                y_train,
                mode="classification",
                seed=0,
                {override_name}="{plugin_identifier}",
            )
            collection = explainer.{explain_method}(x_test[:2])
            assert collection.explanations
            assert len(collection.explanations) == 2
            assert (
                explainer.plugin_manager.explanation_plugin_identifiers["{mode}"]
                == "{plugin_identifier}"
            )
        """
    )
    entry_point_block = dedent(
        f"""\
        [project.entry-points."{entrypoint_group}"]
        {entry_name} = "{import_name}.plugin:{class_name}"
        """
    ).strip()
    return init_py, plugin_py, test_py, entry_point_block


def build_visualization_files(
    *,
    slug: str,
    import_name: str,
    plugin_identifier: str,
    capabilities: list[str],
    version: str,
    provider: str,
) -> tuple[str, str, str, str]:
    prefix = "".join(part.capitalize() for part in slug.split("-"))
    builder_name = f"{prefix}PlotBuilder"
    renderer_name = f"{prefix}PlotRenderer"
    bootstrap_name = f"{prefix}VisualizationBootstrap"
    entry_name = slug.replace("-", "_")
    style_name = plugin_identifier
    builder_identifier = f"{plugin_identifier}.builder"
    renderer_identifier = f"{plugin_identifier}.renderer"
    bootstrap_identifier = f"{plugin_identifier}.bootstrap"
    init_py = dedent(
        f"""\
        \"\"\"Package for {import_name}.\"\"\"

        from .plugin import {bootstrap_name}, {builder_name}, {renderer_name}

        __all__ = ["{bootstrap_name}", "{builder_name}", "{renderer_name}"]
        """
    )
    plugin_py = dedent(
        f"""\
        from __future__ import annotations

        from calibrated_explanations.plugins.builtins import (
            PlotSpecDefaultBuilder,
            PlotSpecDefaultRenderer,
        )
        from calibrated_explanations.plugins.plots import (
            PlotArtifact,
            PlotBuilder,
            PlotRenderContext,
            PlotRenderResult,
            PlotRenderer,
        )
        from calibrated_explanations.plugins.registry import (
            find_plot_builder_descriptor,
            find_plot_renderer_descriptor,
            find_plot_style_descriptor,
            register_plot_builder,
            register_plot_renderer,
            register_plot_style,
        )


        STYLE_ID = "{style_name}"
        BUILDER_ID = "{builder_identifier}"
        RENDERER_ID = "{renderer_identifier}"
        BOOTSTRAP_ID = "{bootstrap_identifier}"


        class {builder_name}(PlotBuilder):
            \"\"\"Delegating PlotSpec builder registered through the CE style chain.\"\"\"

            plugin_meta = {{
                "schema_version": 1,
                "name": BUILDER_ID,
                "version": "{version}",
                "provider": "{provider}",
                "data_modalities": ("tabular",),
                "style": STYLE_ID,
                "output_formats": ("png", "svg"),
                "capabilities": {capabilities},
                "dependencies": ("plot_spec.default",),
                "trusted": False,
                "trust": False,
                "legacy_compatible": False,
                "default_renderer": RENDERER_ID,
                "config_schema": {{
                    "version": 1,
                    "additional_properties": False,
                    "keys": {{
                        "colorway": {{"type": "list[str]", "default": []}},
                    }},
                }},
            }}

            def __init__(self) -> None:
                self._delegate = PlotSpecDefaultBuilder()

            def build(self, context: PlotRenderContext) -> PlotArtifact:
                return self._delegate.build(context)


        class {renderer_name}(PlotRenderer):
            \"\"\"Delegating PlotSpec renderer registered through the CE style chain.\"\"\"

            plugin_meta = {{
                "schema_version": 1,
                "name": RENDERER_ID,
                "version": "{version}",
                "provider": "{provider}",
                "data_modalities": ("tabular",),
                "output_formats": ("png", "svg"),
                "capabilities": ["plot:renderer"],
                "dependencies": ("plot_spec.default",),
                "trusted": False,
                "trust": False,
                "supports_interactive": False,
            }}

            def __init__(self) -> None:
                self._delegate = PlotSpecDefaultRenderer()

            def render(
                self,
                artifact: PlotArtifact,
                *,
                context: PlotRenderContext,
            ) -> PlotRenderResult:
                return self._delegate.render(artifact, context=context)


        class {bootstrap_name}:
            \"\"\"Bootstrap entry point that registers the style and renderer chain.\"\"\"

            plugin_meta = {{
                "schema_version": 1,
                "name": BOOTSTRAP_ID,
                "version": "{version}",
                "provider": "{provider}",
                "data_modalities": ("tabular",),
                "capabilities": ["plot:bootstrap"],
                "trusted": False,
                "trust": False,
            }}


        def register_scaffold_visualization_components() -> None:
            if find_plot_builder_descriptor(BUILDER_ID) is None:
                register_plot_builder(BUILDER_ID, {builder_name}(), source="entrypoint")
            if find_plot_renderer_descriptor(RENDERER_ID) is None:
                register_plot_renderer(RENDERER_ID, {renderer_name}(), source="entrypoint")
            if find_plot_style_descriptor(STYLE_ID) is None:
                register_plot_style(
                    STYLE_ID,
                    metadata={{
                        "style": STYLE_ID,
                        "builder_id": BUILDER_ID,
                        "renderer_id": RENDERER_ID,
                        "fallbacks": ("plot_spec.default",),
                        "legacy_compatible": False,
                        "is_default": False,
                        "default_for": (),
                    }},
                )


        register_scaffold_visualization_components()
        """
    )
    test_py = dedent(
        f"""\
        import warnings

        import pytest

        pytest.importorskip("calibrated_explanations")

        from calibrated_explanations import CalibratedExplainer
        import calibrated_explanations.plugins.registry as registry
        from sklearn.datasets import make_classification
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split

        BOOTSTRAP_ID = "{bootstrap_identifier}"
        BUILDER_ID = "{builder_identifier}"
        RENDERER_ID = "{renderer_identifier}"
        STYLE_ID = "{style_name}"


        def _reset_registry_state() -> None:
            reset_catalog = getattr(registry, "reset_plugin_catalog", None)
            if callable(reset_catalog):
                reset_catalog(kind="all")
            clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
            if callable(clear_env_cache):
                clear_env_cache()
            clear_warnings = getattr(registry, "clear_trust_warnings", None)
            if callable(clear_warnings):
                clear_warnings()


        def test_plugin_should_be_runtime_consumable(monkeypatch):
            monkeypatch.setenv(
                "CE_TRUST_PLUGIN",
                ",".join(
                    [
                        "{import_name}.plugin:{bootstrap_name}",
                        BOOTSTRAP_ID,
                        BUILDER_ID,
                        RENDERER_ID,
                    ]
                ),
            )
            _reset_registry_state()
            registry.load_entrypoint_plugins(include_untrusted=False)

            builder = registry.find_plot_builder_descriptor(BUILDER_ID)
            renderer = registry.find_plot_renderer_descriptor(RENDERER_ID)
            style = registry.find_plot_style_descriptor(STYLE_ID)
            assert builder is not None
            assert builder.trusted is True
            assert renderer is not None
            assert renderer.trusted is True
            assert style is not None
            assert style.metadata["builder_id"] == BUILDER_ID
            assert style.metadata["renderer_id"] == RENDERER_ID
            assert registry.find_plot_plugin_trusted(STYLE_ID) is not None

            x, y = make_classification(
                n_samples=80,
                n_features=6,
                n_informative=4,
                n_redundant=0,
                random_state=0,
            )
            x_train, x_test, y_train, _ = train_test_split(
                x, y, test_size=0.2, random_state=0, stratify=y
            )
            learner = LogisticRegression(random_state=0, solver="liblinear")
            learner.fit(x_train, y_train)

            explainer = CalibratedExplainer(learner, x_train, y_train, mode="classification", seed=0)
            explanations = explainer.explain_factual(x_test[:1])
            assert explanations.explanations

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                explanations.plot(style=STYLE_ID, show=False)
            fallback_warnings = [
                str(item.message)
                for item in caught
                if "falling back to default" in str(item.message).lower()
                or "failed to find plot renderer" in str(item.message).lower()
            ]
            assert fallback_warnings == []
        """
    )
    entry_point_block = dedent(
        f"""\
        [project.entry-points."{MAIN_ENTRYPOINT_GROUP}"]
        {entry_name} = "{import_name}.plugin:{bootstrap_name}"

        [project.entry-points."calibrated_explanations.plugins.plot_builders"]
        {entry_name} = "{import_name}.plugin:{builder_name}"

        [project.entry-points."calibrated_explanations.plugins.plot_renderers"]
        {entry_name} = "{import_name}.plugin:{renderer_name}"
        """
    ).strip()
    return init_py, plugin_py, test_py, entry_point_block


def infer_interval_modes(capabilities: list[str]) -> tuple[str, ...]:
    modes: list[str] = []
    if any("classification" in capability for capability in capabilities):
        modes.append("classification")
    if any("regression" in capability for capability in capabilities):
        modes.append("regression")
    return tuple(modes or ["classification"])


def infer_single_explanation_mode(capabilities: list[str]) -> str:
    modes = infer_explanation_modes(capabilities)
    if len(modes) != 1:
        raise SystemExit(
            "Official explanation scaffolds require exactly one explanation mode capability"
        )
    return modes[0]


def infer_explanation_modes(capabilities: list[str]) -> tuple[str, ...]:
    modes: list[str] = []
    for candidate in ("factual", "alternative", "fast"):
        prefix = f"explanation:{candidate}"
        if any(capability == prefix for capability in capabilities):
            modes.append(candidate)
    return tuple(modes or ["factual"])


def infer_explanation_tasks(capabilities: list[str]) -> tuple[str, ...]:
    tasks: list[str] = []
    if any(capability == "task:classification" for capability in capabilities):
        tasks.append("classification")
    if any(capability == "task:regression" for capability in capabilities):
        tasks.append("regression")
    return tuple(tasks or ["classification"])


def normalize_explanation_capabilities(
    capabilities: list[str],
    mode: str,
    tasks: tuple[str, ...],
) -> list[str]:
    normalized = list(capabilities)
    for required in ("explain", f"explanation:{mode}", *[f"task:{task}" for task in tasks]):
        if required not in normalized:
            normalized.append(required)
    return normalized


def explanation_delegate(mode: str) -> tuple[str, str]:
    if mode == "factual":
        return (
            "from calibrated_explanations.plugins.builtins import LegacyFactualExplanationPlugin",
            "self._delegate = LegacyFactualExplanationPlugin()",
        )
    if mode == "alternative":
        return (
            "from calibrated_explanations.plugins.builtins import LegacyAlternativeExplanationPlugin",
            "self._delegate = LegacyAlternativeExplanationPlugin()",
        )
    if mode == "fast":
        return (
            dedent(
                """\
                from calibrated_explanations.plugins.explanations_fast import register_fast_explanation_plugin
                from calibrated_explanations.plugins.registry import find_explanation_descriptor
                """
            ).strip(),
            dedent(
                """\
                register_fast_explanation_plugin()
                descriptor = find_explanation_descriptor("core.explanation.fast")
                if descriptor is None:
                    raise RuntimeError("FAST explanation plugin registration failed")
                self._delegate = descriptor.plugin
                """
            ).strip(),
        )
    raise SystemExit(f"Unsupported explanation mode: {mode}")


def explanation_api_method(mode: str) -> str:
    if mode == "factual":
        return "explain_factual"
    if mode == "alternative":
        return "explore_alternatives"
    if mode == "fast":
        return "explain_fast"
    raise SystemExit(f"Unsupported explanation mode: {mode}")


def explanation_override_name(mode: str) -> str:
    if mode == "factual":
        return "factual_plugin"
    if mode == "alternative":
        return "alternative_plugin"
    if mode == "fast":
        return "fast_plugin"
    raise SystemExit(f"Unsupported explanation mode: {mode}")


def write_meta_package(
    *,
    package_dir: Path,
    distribution_name: str,
    ce_range: str,
    version: str,
) -> None:
    package_dir.mkdir(parents=True)
    # The umbrella metapackage aggregates the family metapackages. Family
    # metapackages start empty: only plugins with status = "mature" may be
    # curated into them, and curation is a deliberate review decision.
    dependency_map = {
        "calibrated-explanations-plugins": [
            "calibrated-explanations-calibration",
            "calibrated-explanations-explanation",
            "calibrated-explanations-visualization",
        ],
    }
    dependency_lines = ",\n    ".join(
        f'"{dependency}{ce_range}"' for dependency in dependency_map.get(distribution_name, [])
    )
    if not dependency_lines:
        dependency_lines = (
            '# Curation policy: only plugins with status = "mature" may be listed here.'
        )
    pyproject = dedent(
        f"""\
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "{distribution_name}"
        version = "{version}"
        description = "Curated metapackage for calibrated-explanations plugins"
        readme = "README.md"
        requires-python = ">=3.11"
        dependencies = [
            {dependency_lines}
        ]

        [tool.hatch.build.targets.wheel]
        bypass-selection = true

        [tool.ce_plugin_repo]
        family = "meta"
        """
    )
    readme = dedent(
        f"""\
        # {distribution_name}

        Family: `meta`

        Purpose: Curated metapackage for the calibrated-explanations plugin ecosystem.
        It installs only plugins that have completed a maturity review and were
        explicitly selected for the recommended default set.

        Install:

        ```bash
        pip install {distribution_name}
        ```

        Compatibility: `calibrated-explanations{ce_range}`

        Upstream docs:

        - CE Read the Docs: <{DOCS_HOME}>
        """
    )
    (package_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (package_dir / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
