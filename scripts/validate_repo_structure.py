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

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from lifecycle import ALLOWED_STATUSES  # noqa: E402

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
CONFIG_SCHEMA_TYPES = {
    "str",
    "int",
    "float",
    "bool",
    "list",
    "list[str]",
    "mapping",
}
CANONICAL_DATA_MODALITIES = {"tabular", "vision", "audio"}


@dataclass
class PackageInfo:
    root: Path
    family: str
    package_type: str
    name: str
    version: str
    status: str | None
    import_name: str | None
    entry_points: dict[str, dict[str, str]]


def validate_repository(root: Path | None = None) -> list[str]:
    """Run all repository checks, optionally against an alternate repo root."""
    global ROOT, PACKAGES_DIR
    previous = (ROOT, PACKAGES_DIR)
    if root is not None:
        ROOT = root
        PACKAGES_DIR = root / "packages"
    try:
        errors: list[str] = []
        packages = discover_packages(errors)
        check_uniqueness(packages, errors)
        check_cross_package_imports(packages, errors)
        return errors
    finally:
        ROOT, PACKAGES_DIR = previous


def main() -> int:
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Repository structure validation passed.")
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
                errors.append(
                    f"Unexpected file in {family_dir.relative_to(ROOT)}: {package_dir.name}"
                )
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

    import_name = tool_cfg.get("import_name") if isinstance(tool_cfg, dict) else None
    status = tool_cfg.get("status") if isinstance(tool_cfg, dict) else None
    dependencies = project.get("dependencies", [])
    entry_points = {
        group: dict(project.get("entry-points", {}).get(group, {})) for group in ENTRYPOINT_GROUPS
    }

    if family == "meta":
        validate_meta_package(package_dir, name, dependencies, errors)
    else:
        validate_plugin_package(
            package_dir=package_dir,
            family=family,
            name=name,
            import_name=import_name,
            entry_points=entry_points,
            dependencies=dependencies,
            errors=errors,
        )
    validate_readme(
        readme_path,
        name,
        status if family != "meta" else None,
        errors,
    )
    return PackageInfo(
        root=package_dir,
        family=family,
        package_type="meta" if family == "meta" else "plugin",
        name=name,
        version=version,
        status=status if isinstance(status, str) else None,
        import_name=import_name,
        entry_points=entry_points,
    )


def validate_meta_package(
    package_dir: Path,
    name: str,
    dependencies: list[str],
    errors: list[str],
) -> None:
    if name not in META_PACKAGES:
        errors.append(f"{package_dir.relative_to(ROOT)} has invalid meta-package name {name!r}")
    if (package_dir / "src").exists():
        errors.append(f"{package_dir.relative_to(ROOT)} meta-package must not contain src/")
    if (package_dir / "tests").exists():
        errors.append(f"{package_dir.relative_to(ROOT)} meta-package must not contain tests/")
    # The umbrella metapackage must aggregate the family metapackages. Family
    # metapackages may legitimately be empty while no plugin is mature.
    if name == "calibrated-explanations-plugins" and not dependencies:
        errors.append(
            f"{package_dir.relative_to(ROOT)} umbrella metapackage must depend on "
            "the family metapackages"
        )


def validate_plugin_package(
    *,
    package_dir: Path,
    family: str,
    name: str,
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
        errors.append(
            f"{package_dir.relative_to(ROOT)} package name uses disallowed plot/viz alias"
        )
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
        errors.append(
            f"{package_dir.relative_to(ROOT)} must declare at least one CE entry-point group"
        )
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
    module_constants = collect_module_constants(tree, module_path)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == object_name:
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and target.id == "plugin_meta":
                            return resolve_static_value(statement.value, module_constants)
                if (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == "plugin_meta"
                    and statement.value is not None
                ):
                    return resolve_static_value(statement.value, module_constants)
    return None


def collect_module_constants(
    tree: ast.Module, module_path: Path | None = None
) -> dict[str, object]:
    constants: dict[str, object] = {}
    if module_path is not None:
        constants.update(collect_imported_metadata_constants(tree, module_path))
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


def collect_imported_metadata_constants(tree: ast.Module, module_path: Path) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        # Follow sibling-module imports within the same package (e.g.
        # ``from .metadata import X`` or ``from ._version import Y``) so
        # plugin_meta may reference package-level constants.
        leaf = node.module.rsplit(".", 1)[-1]
        metadata_path = module_path.with_name(f"{leaf}.py")
        if not metadata_path.exists():
            continue
        metadata_tree = ast.parse(
            metadata_path.read_text(encoding="utf-8"), filename=str(metadata_path)
        )
        metadata_constants = collect_module_constants(metadata_tree)
        for alias in node.names:
            imported_name = alias.name
            local_name = alias.asname or alias.name
            if imported_name in metadata_constants:
                constants[local_name] = metadata_constants[imported_name]
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
            for key, value in zip(node.keys, node.values, strict=False)
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


def validate_plugin_meta(
    package_dir: Path, family: str, plugin_meta: dict, errors: list[str]
) -> None:
    required = {
        "schema_version",
        "name",
        "version",
        "provider",
        "data_modalities",
        "capabilities",
        "trusted",
    }
    missing = required - set(plugin_meta)
    if missing:
        errors.append(
            f"{package_dir.relative_to(ROOT)} plugin_meta missing keys: {sorted(missing)}"
        )
        return
    if plugin_meta["schema_version"] != 1:
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta.schema_version must be 1")
    if not isinstance(plugin_meta["name"], str) or not PLUGIN_ID_PATTERN.match(plugin_meta["name"]):
        errors.append(f"{package_dir.relative_to(ROOT)} plugin_meta.name is invalid")
    validate_data_modalities(package_dir, plugin_meta["data_modalities"], errors)
    if (
        not isinstance(plugin_meta["capabilities"], (list, tuple))
        or not plugin_meta["capabilities"]
    ):
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
    if "config_schema" in plugin_meta:
        validate_plugin_config_schema(package_dir, plugin_meta["config_schema"], errors)


def validate_data_modalities(package_dir: Path, modalities: object, errors: list[str]) -> None:
    prefix = f"{package_dir.relative_to(ROOT)} plugin_meta.data_modalities"
    if (
        isinstance(modalities, str)
        or not isinstance(modalities, (list, tuple))
        or not modalities
    ):
        errors.append(f"{prefix} must be a non-empty sequence")
        return
    invalid = [
        modality
        for modality in modalities
        if not isinstance(modality, str)
        or (modality not in CANONICAL_DATA_MODALITIES and not modality.startswith("x-"))
    ]
    if invalid:
        errors.append(
            f"{prefix} must contain canonical modalities "
            f"{sorted(CANONICAL_DATA_MODALITIES)} or 'x-' extension modalities"
        )


def validate_plugin_config_schema(package_dir: Path, schema: object, errors: list[str]) -> None:
    """Validate the provisional plugin config schema shape used by official examples."""
    prefix = f"{package_dir.relative_to(ROOT)} plugin_meta.config_schema"
    if not isinstance(schema, dict):
        errors.append(f"{prefix} must be a mapping")
        return
    version = schema.get("version", 1)
    if version != 1:
        errors.append(f"{prefix}.version must be 1")
    additional_properties = schema.get("additional_properties", False)
    if not isinstance(additional_properties, bool):
        errors.append(f"{prefix}.additional_properties must be boolean")
    keys = schema.get("keys", schema.get("properties", {}))
    if not isinstance(keys, dict):
        errors.append(f"{prefix}.keys must be a mapping")
        return
    for key, entry in keys.items():
        if not isinstance(key, str) or not key:
            errors.append(f"{prefix}.keys names must be non-empty strings")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{prefix}.keys[{key!r}] must be a mapping")
            continue
        raw_type = entry.get("type")
        if raw_type not in CONFIG_SCHEMA_TYPES:
            errors.append(
                f"{prefix}.keys[{key!r}].type must be one of {sorted(CONFIG_SCHEMA_TYPES)}"
            )
        if "required" in entry and not isinstance(entry["required"], bool):
            errors.append(f"{prefix}.keys[{key!r}].required must be boolean")
        if "sensitive" in entry and not isinstance(entry["sensitive"], bool):
            errors.append(f"{prefix}.keys[{key!r}].sensitive must be boolean")
        choices = entry.get("choices")
        if choices is not None and (
            isinstance(choices, str) or not isinstance(choices, (list, tuple))
        ):
            errors.append(f"{prefix}.keys[{key!r}].choices must be a sequence")
        if "default" in entry and raw_type in CONFIG_SCHEMA_TYPES:
            validate_plugin_config_default(
                package_dir,
                key,
                entry["default"],
                str(raw_type),
                errors,
            )


def validate_plugin_config_default(
    package_dir: Path,
    key: str,
    value: object,
    raw_type: str,
    errors: list[str],
) -> None:
    prefix = f"{package_dir.relative_to(ROOT)} " f"plugin_meta.config_schema.keys[{key!r}].default"
    if raw_type == "str" and not isinstance(value, str):
        errors.append(f"{prefix} must be str")
    elif raw_type == "int" and (not isinstance(value, int) or isinstance(value, bool)):
        errors.append(f"{prefix} must be int")
    elif raw_type == "float" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        errors.append(f"{prefix} must be float")
    elif raw_type == "bool" and not isinstance(value, bool):
        errors.append(f"{prefix} must be bool")
    elif raw_type == "list" and not isinstance(value, (list, tuple)):
        errors.append(f"{prefix} must be a list-like sequence")
    elif raw_type == "list[str]" and (
        not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value)
    ):
        errors.append(f"{prefix} must be a sequence of strings")
    elif raw_type == "mapping" and not isinstance(value, dict):
        errors.append(f"{prefix} must be a mapping")


def _has_bare_pypi_install(text: str, package_name: str) -> bool:
    return any(line.strip() == f"pip install {package_name}" for line in text.splitlines())


def validate_readme(
    readme_path: Path,
    package_name: str,
    status: str | None,
    errors: list[str],
) -> None:
    """Validate the structural facts a README must not contradict.

    Only stable facts are checked (status agreement, install-command presence,
    deprecation heading); recommended prose lives in templates, not in policy.
    """
    text = readme_path.read_text(encoding="utf-8")
    rel = readme_path.relative_to(ROOT)
    if status is None:  # metapackage; lifecycle.py validates its curation
        return
    if status in ALLOWED_STATUSES and f"Status: `{status}`" not in text:
        errors.append(
            f"{rel} must declare a 'Status: `{status}`' line matching "
            "tool.ce_plugin_repo.status"
        )
    if status == "mature" and not _has_bare_pypi_install(text, package_name):
        errors.append(
            f"{rel} is mature and must document PyPI installation with a plain "
            f"'pip install {package_name}' command"
        )
    elif status == "experimental" and _has_bare_pypi_install(text, package_name):
        errors.append(
            f"{rel} is experimental and must not advertise 'pip install "
            f"{package_name}'; experimental plugins are not published to PyPI"
        )
    elif status == "deprecated" and "**Deprecated**" not in text and "# Deprecated" not in text:
        errors.append(
            f"{rel} is deprecated and must carry a visible '**Deprecated**' notice "
            "with migration guidance"
        )


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
    known_imports = {
        package.import_name: package for package in plugin_packages if package.import_name
    }
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
