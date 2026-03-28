from __future__ import annotations

import argparse
import importlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def require_callable(obj: object, attribute: str, package_path: Path, entry_name: str) -> None:
    member = getattr(obj, attribute, None)
    if not callable(member):
        raise RuntimeError(
            f"{package_path} entry point {entry_name!r} must expose callable {attribute!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test package entry points.")
    parser.add_argument("package_path")
    args = parser.parse_args()

    package_path = Path(args.package_path)
    pyproject_path = package_path / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)

    from calibrated_explanations.plugins.base import validate_plugin_meta
    from calibrated_explanations.plugins.registry import (
        find_explanation_descriptor,
        find_interval_descriptor,
        find_plot_builder_descriptor,
        find_plot_renderer_descriptor,
        find_plot_style_descriptor,
        validate_explanation_metadata,
        validate_interval_metadata,
        validate_plot_builder_metadata,
        validate_plot_renderer_metadata,
    )

    family = data.get("tool", {}).get("ce_plugin_repo", {}).get("family")
    entry_points = data.get("project", {}).get("entry-points", {})
    if family == "visualization":
        required_groups = {
            "calibrated_explanations.plugins",
            "calibrated_explanations.plugins.plot_builders",
            "calibrated_explanations.plugins.plot_renderers",
        }
        present_groups = {group for group, entries in entry_points.items() if entries}
        if present_groups != required_groups:
            raise RuntimeError(
                f"{package_path} must expose both plot builder and plot renderer entry points"
            )

    for group_name, group_entries in entry_points.items():
        if not group_name.startswith("calibrated_explanations.plugins"):
            continue
        for entry_name, target in group_entries.items():
            module_name, _, object_name = target.partition(":")
            module = importlib.import_module(module_name)
            plugin_object = getattr(module, object_name)
            plugin_meta = getattr(plugin_object, "plugin_meta", None)
            if plugin_meta is None:
                raise RuntimeError(
                    f"{package_path} entry point {entry_name!r} does not expose plugin_meta"
                )
            validate_plugin_meta(dict(plugin_meta))
            if group_name == "calibrated_explanations.plugins":
                if family == "calibration":
                    require_callable(plugin_object, "create", package_path, entry_name)
                    validate_interval_metadata(dict(plugin_meta))
                    if find_interval_descriptor(str(plugin_meta["name"])) is None:
                        raise RuntimeError(
                            f"{package_path} did not register interval descriptor {plugin_meta['name']!r}"
                        )
                elif family == "explanation":
                    require_callable(plugin_object, "supports", package_path, entry_name)
                    require_callable(plugin_object, "supports_mode", package_path, entry_name)
                    require_callable(plugin_object, "initialize", package_path, entry_name)
                    require_callable(plugin_object, "explain_batch", package_path, entry_name)
                    validate_explanation_metadata(dict(plugin_meta))
                    if find_explanation_descriptor(str(plugin_meta["name"])) is None:
                        raise RuntimeError(
                            f"{package_path} did not register explanation descriptor {plugin_meta['name']!r}"
                        )
                elif family == "visualization":
                    style_id = getattr(module, "STYLE_ID", None)
                    builder_id = getattr(module, "BUILDER_ID", None)
                    renderer_id = getattr(module, "RENDERER_ID", None)
                    if not isinstance(style_id, str) or find_plot_style_descriptor(style_id) is None:
                        raise RuntimeError(
                            f"{package_path} visualization bootstrap did not register a plot style"
                        )
                    if not isinstance(builder_id, str) or find_plot_builder_descriptor(builder_id) is None:
                        raise RuntimeError(
                            f"{package_path} visualization bootstrap did not register a plot builder"
                        )
                    if not isinstance(renderer_id, str) or find_plot_renderer_descriptor(renderer_id) is None:
                        raise RuntimeError(
                            f"{package_path} visualization bootstrap did not register a plot renderer"
                        )
            elif group_name == "calibrated_explanations.plugins.plot_builders":
                require_callable(plugin_object, "build", package_path, entry_name)
                validate_plot_builder_metadata(dict(plugin_meta))
            elif group_name == "calibrated_explanations.plugins.plot_renderers":
                require_callable(plugin_object, "render", package_path, entry_name)
                validate_plot_renderer_metadata(dict(plugin_meta))
    print(f"Smoke test passed for {package_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
