from __future__ import annotations

import ast
import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
MAIN_GROUP = "calibrated_explanations.plugins"
PLOT_BUILDER_GROUP = "calibrated_explanations.plugins.plot_builders"
PLOT_RENDERER_GROUP = "calibrated_explanations.plugins.plot_renderers"


def load_package_metadata(package_path: Path) -> dict[str, Any]:
    with (package_path / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def package_family(package_path: Path) -> str:
    data = load_package_metadata(package_path)
    family = data.get("tool", {}).get("ce_plugin_repo", {}).get("family")
    if family not in PLUGIN_FAMILIES:
        raise RuntimeError(f"{package_path} does not declare a supported plugin family")
    return family


def entry_points_for_group(package_path: Path, group_name: str) -> dict[str, str]:
    data = load_package_metadata(package_path)
    return dict(data.get("project", {}).get("entry-points", {}).get(group_name, {}))


def load_entrypoint_target(target: str) -> Any:
    import importlib

    module_name, _, object_name = target.partition(":")
    if not module_name or not object_name:
        raise RuntimeError(f"Invalid entry point target {target!r}")
    module = importlib.import_module(module_name)
    return getattr(module, object_name)


def module_path_for_target(package_path: Path, target: str) -> Path:
    import_name = str(load_package_metadata(package_path)["tool"]["ce_plugin_repo"]["import_name"])
    module_name, _, _ = target.partition(":")
    if not module_name:
        raise RuntimeError(f"Invalid entry point target {target!r}")
    relative_parts = module_name.split(".")
    if relative_parts[0] != import_name:
        relative_parts.insert(0, import_name)
    return package_path / "src" / Path(*relative_parts).with_suffix(".py")


def _collect_module_constants(tree: ast.Module) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            constants[node.targets[0].id] = _resolve_static_value(node.value, constants)
        except ValueError:
            continue
    return constants


def _resolve_static_value(node: ast.AST, constants: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_resolve_static_value(item, constants) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_resolve_static_value(item, constants) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _resolve_static_value(key, constants): _resolve_static_value(value, constants)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Name):
        if node.id in constants:
            return constants[node.id]
        raise ValueError(f"Unresolved constant {node.id!r}")
    raise ValueError(f"Unsupported static expression: {ast.dump(node, include_attributes=False)}")


def static_plugin_meta(package_path: Path, target: str) -> dict[str, Any]:
    module_path = module_path_for_target(package_path, target)
    _, _, object_name = target.partition(":")
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    constants = _collect_module_constants(tree)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == object_name:
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for assign_target in statement.targets:
                        if isinstance(assign_target, ast.Name) and assign_target.id == "plugin_meta":
                            resolved = _resolve_static_value(statement.value, constants)
                            if isinstance(resolved, dict):
                                return dict(resolved)
    raise RuntimeError(f"Could not statically resolve plugin_meta for {target!r}")


def primary_plugin_target(package_path: Path) -> Any:
    main_group = entry_points_for_group(package_path, MAIN_GROUP)
    if len(main_group) != 1:
        raise RuntimeError(f"{package_path} must expose exactly one main plugin entry point")
    return load_entrypoint_target(next(iter(main_group.values())))


def main_plugin_meta(package_path: Path) -> dict[str, Any]:
    target = primary_plugin_target(package_path)
    plugin_meta = getattr(target, "plugin_meta", None)
    if plugin_meta is None:
        raise RuntimeError(f"{package_path} main entry point does not expose plugin_meta")
    return dict(plugin_meta)


def visualization_metas(package_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bootstrap = main_plugin_meta(package_path)
    builder_entries = entry_points_for_group(package_path, PLOT_BUILDER_GROUP)
    renderer_entries = entry_points_for_group(package_path, PLOT_RENDERER_GROUP)
    if len(builder_entries) != 1 or len(renderer_entries) != 1:
        raise RuntimeError(f"{package_path} must expose exactly one builder and one renderer")
    builder_meta = dict(getattr(load_entrypoint_target(next(iter(builder_entries.values()))), "plugin_meta"))
    renderer_meta = dict(
        getattr(load_entrypoint_target(next(iter(renderer_entries.values()))), "plugin_meta")
    )
    return bootstrap, builder_meta, renderer_meta


def configure_trust(package_path: Path) -> None:
    family = package_family(package_path)
    main_entries = entry_points_for_group(package_path, MAIN_GROUP)
    trust_ids: list[str] = list(main_entries.values())
    if family == "visualization":
        bootstrap_target = next(iter(main_entries.values()))
        bootstrap_meta = static_plugin_meta(package_path, bootstrap_target)
        builder_target = next(
            iter(entry_points_for_group(package_path, PLOT_BUILDER_GROUP).values())
        )
        renderer_target = next(
            iter(entry_points_for_group(package_path, PLOT_RENDERER_GROUP).values())
        )
        builder_meta = static_plugin_meta(package_path, builder_target)
        renderer_meta = static_plugin_meta(package_path, renderer_target)
        trust_ids.extend(
            [
                str(bootstrap_meta["name"]),
                str(builder_meta["name"]),
                str(renderer_meta["name"]),
            ]
        )
    else:
        trust_ids.append(str(static_plugin_meta(package_path, next(iter(main_entries.values())))["name"]))

    os.environ["CE_TRUST_PLUGIN"] = ",".join(trust_ids)

    import calibrated_explanations.plugins.registry as registry

    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()
    clear_warnings = getattr(registry, "clear_trust_warnings", None)
    if callable(clear_warnings):
        clear_warnings()
    registry.load_entrypoint_plugins(include_untrusted=False)


def make_classification_fixture() -> tuple["np.ndarray", "np.ndarray", "np.ndarray", "np.ndarray"]:
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split

    x, y = make_classification(
        n_samples=120,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=0, stratify=y
    )
    return x_train, x_test, y_train, y_test


def make_regression_fixture() -> tuple["np.ndarray", "np.ndarray", "np.ndarray", "np.ndarray"]:
    from sklearn.datasets import make_regression
    from sklearn.model_selection import train_test_split

    x, y = make_regression(
        n_samples=120,
        n_features=6,
        n_informative=4,
        noise=0.5,
        random_state=0,
    )
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=0)
    return x_train, x_test, y_train, y_test


def build_explainer(*, task: str, **kwargs: Any):
    from calibrated_explanations import CalibratedExplainer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LogisticRegression

    if task == "classification":
        x_train, x_test, y_train, _ = make_classification_fixture()
        learner = LogisticRegression(random_state=0, solver="liblinear")
    else:
        x_train, x_test, y_train, _ = make_regression_fixture()
        learner = RandomForestRegressor(n_estimators=16, random_state=0)
    learner.fit(x_train, y_train)
    explainer = CalibratedExplainer(learner, x_train, y_train, mode=task, seed=0, **kwargs)
    return explainer, x_test[:3]


def assert_non_empty_collection(collection: Any) -> None:
    explanations = getattr(collection, "explanations", None)
    if not explanations:
        raise RuntimeError("Expected a non-empty explanation collection")


def validate_calibration_runtime(package_path: Path) -> None:
    import numpy as np

    from calibrated_explanations.plugins.registry import find_interval_descriptor

    meta = main_plugin_meta(package_path)
    plugin_id = str(meta["name"])
    descriptor = find_interval_descriptor(plugin_id)
    if descriptor is None or not descriptor.trusted:
        raise RuntimeError(f"Interval plugin {plugin_id!r} was not registered as trusted")

    modes = tuple(meta.get("modes", ()))
    tasks = ("classification", "regression") if "regression" in modes else ("classification",)
    for task in tasks:
        explainer, x_test = build_explainer(task=task, interval_plugin=plugin_id)
        prediction = explainer.predict(x_test, calibrated=True)
        if np.asarray(prediction).shape[0] != x_test.shape[0]:
            raise RuntimeError(f"Unexpected calibrated prediction shape for task {task!r}")
        if explainer.interval_plugin_identifiers.get("default") != plugin_id:
            raise RuntimeError(f"CE did not select {plugin_id!r} as the active interval plugin")


def _explanation_override_name(mode: str) -> str:
    if mode == "factual":
        return "factual_plugin"
    if mode == "alternative":
        return "alternative_plugin"
    if mode == "fast":
        return "fast_plugin"
    raise RuntimeError(f"Unsupported explanation mode {mode!r}")


def _invoke_explanation(explainer: Any, mode: str, x_test: "np.ndarray"):
    if mode == "factual":
        return explainer.explain_factual(x_test)
    if mode == "alternative":
        return explainer.explore_alternatives(x_test)
    if mode == "fast":
        return explainer.explain_fast(x_test)
    raise RuntimeError(f"Unsupported explanation mode {mode!r}")


def validate_explanation_runtime(package_path: Path) -> None:
    import numpy as np

    from calibrated_explanations.plugins.registry import find_explanation_descriptor

    meta = main_plugin_meta(package_path)
    plugin_id = str(meta["name"])
    descriptor = find_explanation_descriptor(plugin_id)
    if descriptor is None or not descriptor.trusted:
        raise RuntimeError(f"Explanation plugin {plugin_id!r} was not registered as trusted")

    modes = tuple(meta.get("modes", ()))
    tasks = tuple(meta.get("tasks", ("classification",)))
    concrete_tasks = tuple(task for task in tasks if task in ("classification", "regression"))
    if not concrete_tasks:
        concrete_tasks = ("classification",)
    for task in concrete_tasks:
        for mode in modes:
            explainer, x_test = build_explainer(task=task, **{_explanation_override_name(mode): plugin_id})
            collection = _invoke_explanation(explainer, mode, x_test[:2])
            assert_non_empty_collection(collection)
            selected = explainer.plugin_manager.explanation_plugin_identifiers.get(mode)
            if selected != plugin_id:
                raise RuntimeError(
                    f"CE selected explanation plugin {selected!r} instead of {plugin_id!r} for mode {mode!r}"
                )


def validate_visualization_runtime(package_path: Path) -> None:
    from calibrated_explanations.plugins.registry import (
        find_plot_builder_descriptor,
        find_plot_plugin_trusted,
        find_plot_renderer_descriptor,
        find_plot_style_descriptor,
    )

    _, builder_meta, renderer_meta = visualization_metas(package_path)
    style_id = str(builder_meta["style"])
    builder_id = str(builder_meta["name"])
    renderer_id = str(renderer_meta["name"])

    builder_descriptor = find_plot_builder_descriptor(builder_id)
    renderer_descriptor = find_plot_renderer_descriptor(renderer_id)
    style_descriptor = find_plot_style_descriptor(style_id)
    if builder_descriptor is None or not builder_descriptor.trusted:
        raise RuntimeError(f"Plot builder {builder_id!r} was not registered as trusted")
    if renderer_descriptor is None or not renderer_descriptor.trusted:
        raise RuntimeError(f"Plot renderer {renderer_id!r} was not registered as trusted")
    if style_descriptor is None:
        raise RuntimeError(f"Plot style {style_id!r} was not registered")
    if style_descriptor.metadata.get("builder_id") != builder_id:
        raise RuntimeError(f"Plot style {style_id!r} did not resolve builder {builder_id!r}")
    if style_descriptor.metadata.get("renderer_id") != renderer_id:
        raise RuntimeError(f"Plot style {style_id!r} did not resolve renderer {renderer_id!r}")
    if find_plot_plugin_trusted(style_id) is None:
        raise RuntimeError(f"Trusted plot plugin for style {style_id!r} is unavailable")

    explainer, x_test = build_explainer(task="classification")
    collection = explainer.explain_factual(x_test[:1])
    assert_non_empty_collection(collection)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        collection.plot(style=style_id, show=False)
    fallback_warnings = [
        str(item.message)
        for item in caught
        if "falling back to default" in str(item.message).lower()
        or "failed to find plot renderer" in str(item.message).lower()
    ]
    if fallback_warnings:
        raise RuntimeError(
            f"Visualization runtime fell back instead of using style {style_id!r}: {fallback_warnings}"
        )


def validate_runtime(package_path: Path) -> None:
    package_path = package_path.resolve()
    configure_trust(package_path)
    family = package_family(package_path)
    if family == "calibration":
        validate_calibration_runtime(package_path)
    elif family == "explanation":
        validate_explanation_runtime(package_path)
    elif family == "visualization":
        validate_visualization_runtime(package_path)
    else:  # pragma: no cover
        raise RuntimeError(f"Unsupported plugin family {family!r}")
