from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
FAMILY_META_DISTRIBUTIONS = {
    "calibration": "calibrated-explanations-calibration",
    "explanation": "calibrated-explanations-explanation",
    "visualization": "calibrated-explanations-visualization",
}
UMBRELLA_META_DISTRIBUTION = "calibrated-explanations-plugins"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")


def read_project_name(package_dir: Path) -> str:
    with (package_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    name = data.get("project", {}).get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{package_dir} is missing project.name")
    return name


def read_dependency_names(package_dir: Path) -> list[str]:
    with (package_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    dependencies = data.get("project", {}).get("dependencies", [])
    names: list[str] = []
    for dependency in dependencies:
        if not isinstance(dependency, str):
            continue
        match = NAME_PATTERN.match(dependency.strip())
        if match:
            names.append(match.group(0))
    return names


def _plugin_distribution_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for family in PLUGIN_FAMILIES:
        for package_dir in sorted((PACKAGES_DIR / family).glob("*")):
            if not package_dir.is_dir():
                continue
            pyproject = package_dir / "pyproject.toml"
            if not pyproject.exists():
                continue
            distribution = read_project_name(package_dir)
            if distribution in index:
                first = index[distribution].relative_to(ROOT).as_posix()
                second = package_dir.relative_to(ROOT).as_posix()
                raise RuntimeError(
                    f"Duplicate plugin distribution name {distribution!r} in {first} and {second}."
                )
            index[distribution] = package_dir
    return index


def _meta_distribution_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for package_dir in sorted((PACKAGES_DIR / "meta").glob("*")):
        if not package_dir.is_dir():
            continue
        pyproject = package_dir / "pyproject.toml"
        if not pyproject.exists():
            continue
        distribution = read_project_name(package_dir)
        if distribution in index:
            first = index[distribution].relative_to(ROOT).as_posix()
            second = package_dir.relative_to(ROOT).as_posix()
            raise RuntimeError(
                f"Duplicate metapackage distribution name {distribution!r} in {first} and {second}."
            )
        index[distribution] = package_dir
    return index


def official_plugin_paths_for_meta_distribution(meta_distribution: str) -> list[Path]:
    if meta_distribution == UMBRELLA_META_DISTRIBUTION:
        target_meta = [FAMILY_META_DISTRIBUTIONS[family] for family in PLUGIN_FAMILIES]
    elif meta_distribution in FAMILY_META_DISTRIBUTIONS.values():
        target_meta = [meta_distribution]
    else:
        raise RuntimeError(f"Unsupported metapackage distribution {meta_distribution!r}")

    plugin_index = _plugin_distribution_index()
    meta_index = _meta_distribution_index()
    selected: list[Path] = []
    for distribution_name in target_meta:
        meta_dir = meta_index.get(distribution_name)
        if meta_dir is None:
            raise RuntimeError(f"Could not find metapackage directory for {distribution_name!r}")
        for dependency in read_dependency_names(meta_dir):
            plugin_dir = plugin_index.get(dependency)
            if plugin_dir is None:
                raise RuntimeError(
                    f"Metapackage {distribution_name!r} depends on unknown plugin distribution {dependency!r}"
                )
            selected.append(plugin_dir)

    # Keep deterministic order while removing duplicates.
    unique = sorted({path.resolve() for path in selected})
    return unique
