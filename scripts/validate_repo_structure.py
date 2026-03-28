from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
META_PACKAGES = {
    "calibrated-explanations-plugins",
    "calibrated-explanations-calibration",
    "calibrated-explanations-explanation",
    "calibrated-explanations-visualization",
}
ENTRYPOINT_GROUPS = (
    "calibrated_explanations.plugins",
    "calibrated_explanations.plugins.plot_builders",
    "calibrated_explanations.plugins.plot_renderers",
)
PLUGIN_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
DISALLOWED_ALIAS_PATTERN = re.compile(r"(?:^|[-_])(plot|plots|viz)(?:[-_]|$)")


@dataclass
class PackageInfo:
    root: Path
    family: str
    package_type: str
    name: str
    version: str
    import_name: str | None
    entry_points: dict[str, dict[str, str]]


def main() -> int:
    errors: list[str] = []
    packages = discover_packages(errors)
    check_uniqueness(packages, errors)
    check_cross_package_imports(packages, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(packages)} packages successfully.")
    return 0


def discover_packages(errors: list[str]) -> list[PackageInfo]:
    if not PACKAGES_DIR.exists():
        errors.append("Missing packages/ directory.")
        return []

    packages: list[PackageInfo] = []
    for family_dir in sorted(PACKAGES_DIR.iterdir()):
        if not family_dir.is_dir():
            errors.append(f"Unexpected file in packages/: {family_dir.relative_to(ROOT)}")
            continue
        if family_dir.name not in (*PLUGIN_FAMILIES, "meta"):
            errors.append(f"Unexpected package family directory: {family_dir.relative_to(ROOT)}")
            continue
        for package_dir in sorted(family_dir.iterdir()):
            if not package_dir.is_dir():
                errors.append(f"Unexpected file in {family_dir.relative_to(ROOT)}: {package_dir.name}")
                continue
            info = load_package_info(package_dir, family_dir.name, errors)
            if info:
                packages.append(info)
    return packages


def load_package_info(package_dir: Path, family: str, errors: list[str]) -> PackageInfo | None:
    pyproject_path = package_dir / "pyproject.toml"
    readme_path = package_dir / "README.md"
    if not pyproject_path.exists():
        errors.append(f"{package_dir.relative_to(ROOT)} is missing pyproject.toml")
        return None
    if not readme_path.exists():
        errors.append(f"{package_dir.relative_to(ROOT)} is missing README.md")
        return None

    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)

    project = data.get("project", {})
    tool_cfg = data.get("tool", {}).get("ce_plugin_repo", {})
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str):
        errors.append(f"{pyproject_path.relative_to(ROOT)} missing project.name")
        return None
    if not isinstance(version, str) or not VERSION_PATTERN.match(version):
        errors.append(f"{pyproject_path.relative_to(ROOT)} has invalid project.version")
        return None

    metadata_family = tool_cfg.get("family") if isinstance(tool_cfg, dict) else None
    import_name = tool_cfg.get("import_name") if isinstance(tool_cfg, dict) else None
    dependencies = project.get("dependencies", [])
    entry_points = {
        group: dict(project.get("entry-points", {}).get(group, {})) for group in ENTRYPOINT_GROUPS
    }

    if family == "meta":
        validate_meta_package(package_dir, name, metadata_family, dependencies, errors)
    else:
        validate_plugin_package(
            package_dir=package_dir,
            family=family,
            name=name,
            metadata_family=metadata_family,
            import_name=import_name,
            entry_points=entry_points,
            dependencies=dependencies,
            errors=errors,
        )
    validate_readme(readme_path, name, metadata_family or family, errors)
    return PackageInfo(
        root=package_dir,
        family=family,
        package_type="meta" if family == "meta" else "plugin",
        name=name,
        version=version,
        import_name=import_name,
        entry_points=entry_points,
    )


def validate_meta_package(
    package_dir: Path,
    name: str,
    metadata_family: str | None,
    dependencies: list[str],
    errors: list[str],
) -> None:
    if name not in META_PACKAGES:
        errors.append(f"{package_dir.relative_to(ROOT)} has invalid meta-package name {name!r}")
    if metadata_family != "meta":
        errors.append(f"{package_dir.relative_to(ROOT)} must declare tool.ce_plugin_repo.family = 'meta'")
    if (package_dir / "src").exists():
        errors.append(f"{package_dir.relative_to(ROOT)} meta-package must not contain src/")
    if (package_dir / "tests").exists():
        errors.append(f"{package_dir.relative_to(ROOT)} meta-package must not contain tests/")
    if not dependencies:
        errors.append(f"{package_dir.relative_to(ROOT)} meta-package must declare dependencies")


def validate_plugin_package(
    *,
    package_dir: Path,
    family: str,
    name: str,
    metadata_family: str | None,
    import_name: str | None,
    entry_points: dict[str, dict[str, str]],
    dependencies: list[str],
    errors: list[str],
) -> None:
    expected_prefix = f"calibrated-explanations-{family}-"
    if not name.startswith(expected_prefix):
        errors.append(
            f"{package_dir.relative_to(ROOT)} package name {name!r} must start with {expected_prefix!r}"
        )
    if DISALLOWED_ALIAS_PATTERN.search(name):
        errors.append(f"{package_dir.relative_to(ROOT)} package name uses disallowed plot/viz alias")
    if metadata_family != family:
        errors.append(f"{package_dir.relative_to(ROOT)} must declare family {family!r}")
    if not isinstance(import_name, str) or not import_name:
        errors.append(f"{package_dir.relative_to(ROOT)} missing tool.ce_plugin_repo.import_name")
        return
    if not (package_dir / "src" / import_name).exists():
        errors.append(
            f"{package_dir.relative_to(ROOT)} missing import package directory src/{import_name}"
        )
    if not (package_dir / "tests").exists():
        errors.append(f"{package_dir.relative_to(ROOT)} plugin package must contain tests/")
    if not any(dep.startswith("calibrated-explanations") for dep in dependencies):
        errors.append(f"{package_dir.relative_to(ROOT)} must depend on calibrated-explanations")
    validate_plugin_entry_points(package_dir, family, import_name, entry_points, errors)


def validate_plugin_entry_points(
    package_dir: Path,
    family: str,
    import_name: str,
    entry_points: dict[str, dict[str, str]],
    errors: list[str],
) -> None:
    present_groups = [group for group, entries in entry_points.items() if entries]
    if not present_groups:
        errors.append(f"{package_dir.relative_to(ROOT)} must declare at least one CE entry-point group")
        return
    expected_groups = (
        {
            "calibrated_explanations.plugins",
            "calibrated_explanations.plugins.plot_builders",
            "calibrated_explanations.plugins.plot_renderers",
        }
        if family == "visualization"
        else {"calibrated_explanations.plugins"}
    )
    if set(present_groups) != expected_groups:
        errors.append(
            f"{package_dir.relative_to(ROOT)} entry-point groups {sorted(present_groups)} "
            f"must match {sorted(expected_groups)} for family {family!r}"
        )
    has_valid_meta = False
    for group in present_groups:
        for target in entry_points[group].values():
            plugin_meta = resolve_plugin_meta(package_dir, import_name, target)
            if plugin_meta is None:
                errors.append(
                    f"{package_dir.relative_to(ROOT)} could not statically resolve plugin_meta for {target!r}"
                )
                continue
            validate_plugin_meta(package_dir, family, plugin_meta, errors)
            has_valid_meta = True
    if not has_valid_meta:
        errors.append(f"{package_dir.relative_to(ROOT)} has no statically valid plugin_meta")


def resolve_plugin_meta(package_dir: Path, import_name: str, target: str) -> dict | None:
    module_name, _, object_name = target.partition(":")
    if not module_name or not object_name:
        return None
    relative_parts = module_name.split(".")
    if relative_parts[0] != import_name:
        relative_parts.insert(0, import_name)
    module_path = package_dir / "src" / Path(*relative_parts).with_suffix(".py")
    if not module_path.exists():
        return None
    return extract_plugin_meta(module_path, object_name)


def extract_plugin_meta(module_path: Path, object_name: str) -> dict | None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    module_constants = collect_module_constants(tree)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == object_name:
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and target.id == "plugin_meta":
                            return resolve_static_value(statement.value, module_constants)
    return None


def collect_module_constants(tree: ast.Module) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            constants[node.targets[0].id] = resolve_static_value(node.value, constants)
        except ValueError:
            continue
    return constants


def resolve_static_value(node: ast.AST, constants: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [resolve_static_value(item, constants) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(resolve_static_value(item, constants) for item in node.elts)
    if isinstance(node, ast.Set):
        return {resolve_static_value(item, constants) for item in node.elts}
    if isinstance(node, ast.Dict):
        return {
            resolve_static_value(key, constants): resolve_static_value(value, constants)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Name):
        if node.id in constants:
            return constants[node.id]
        raise ValueError(f"Unresolved constant name: {node.id}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = resolve_static_value(node.operand, constants)
        if not isinstance(operand, (int, float)):
            raise ValueError("Unary operator only supported for numeric literals")
        return +operand if isinstance(node.op, ast.UAdd) else -operand
    raise ValueError(f"Unsupported static expression: {ast.dump(node, include_attributes=False)}")


def validate_plugin_meta(package_dir: Path, family: str, plugin_meta: dict, errors: list[str]) -> None:
    required = {
        "schema_version",
        "name",
        "version",
        "provider",
        "capabilities",
        "trusted",
    }
    missing = required - set(plugin_meta)
    if missing:
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta missing keys: {sorted(missing)}")
        return
    if plugin_meta["schema_version"] != 1:
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta.schema_version must be 1")
    if not isinstance(plugin_meta["name"], str) or not PLUGIN_ID_PATTERN.match(plugin_meta["name"]):
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta.name is invalid")
    if not isinstance(plugin_meta["capabilities"], (list, tuple)) or not plugin_meta["capabilities"]:
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta.capabilities must be non-empty")
        return
    expected_prefix = {
        "calibration": "interval:",
        "explanation": "explanation:",
        "visualization": "plot:",
    }[family]
    if not any(
        isinstance(capability, str) and capability.startswith(expected_prefix)
        for capability in plugin_meta["capabilities"]
    ):
        errors.append(
            f"{package_dir.relative_to(ROOT)} plugin_meta.capabilities must include {expected_prefix!r}"
        )


def validate_readme(readme_path: Path, package_name: str, family: str, errors: list[str]) -> None:
    text = readme_path.read_text(encoding="utf-8")
    if f"pip install {package_name}" not in text:
        errors.append(f"{readme_path.relative_to(ROOT)} must contain an install command")
    if f"Family: `{family}`" not in text:
        errors.append(f"{readme_path.relative_to(ROOT)} must declare Family: `{family}`")
    if "Purpose:" not in text:
        errors.append(f"{readme_path.relative_to(ROOT)} must contain Purpose:")
    if "Compatibility: `calibrated-explanations" not in text:
        errors.append(f"{readme_path.relative_to(ROOT)} must declare calibrated-explanations compatibility")


def check_uniqueness(packages: list[PackageInfo], errors: list[str]) -> None:
    seen_names: dict[str, Path] = {}
    seen_imports: dict[str, Path] = {}
    seen_plugin_ids: dict[str, Path] = {}
    for package in packages:
        previous = seen_names.get(package.name)
        if previous:
            errors.append(
                f"Duplicate package name {package.name!r} in "
                f"{previous.relative_to(ROOT)} and {package.root.relative_to(ROOT)}"
            )
        seen_names[package.name] = package.root
        if package.import_name:
            previous = seen_imports.get(package.import_name)
            if previous:
                errors.append(
                    f"Duplicate import package {package.import_name!r} in "
                    f"{previous.relative_to(ROOT)} and {package.root.relative_to(ROOT)}"
                )
            seen_imports[package.import_name] = package.root
        for group_entries in package.entry_points.values():
            for target in group_entries.values():
                plugin_meta = (
                    resolve_plugin_meta(package.root, package.import_name, target)
                    if package.import_name
                    else None
                )
                if not plugin_meta:
                    continue
                plugin_id = plugin_meta.get("name")
                if not isinstance(plugin_id, str):
                    continue
                previous = seen_plugin_ids.get(plugin_id)
                if previous:
                    errors.append(
                        f"Duplicate plugin identifier {plugin_id!r} in "
                        f"{previous.relative_to(ROOT)} and {package.root.relative_to(ROOT)}"
                    )
                seen_plugin_ids[plugin_id] = package.root


def check_cross_package_imports(packages: list[PackageInfo], errors: list[str]) -> None:
    plugin_packages = [package for package in packages if package.package_type == "plugin"]
    known_imports = {package.import_name: package for package in plugin_packages if package.import_name}
    for package in plugin_packages:
        for python_file in (package.root / "src").rglob("*.py"):
            tree = ast.parse(python_file.read_text(encoding="utf-8"), filename=str(python_file))
            for imported_name in iter_import_names(tree):
                other_package = known_imports.get(imported_name)
                if other_package and other_package.root != package.root:
                    errors.append(
                        f"{python_file.relative_to(ROOT)} must not import sibling package {imported_name!r}"
                    )


def iter_import_names(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.split(".")[0]


if __name__ == "__main__":
    raise SystemExit(main())
