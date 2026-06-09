from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
FAMILY_META_DISTRIBUTIONS = {
    "calibration": "calibrated-explanations-calibration",
    "explanation": "calibrated-explanations-explanation",
    "visualization": "calibrated-explanations-visualization",
}
UMBRELLA_META_DISTRIBUTION = "calibrated-explanations-plugins"


def project_name(package_dir: Path) -> str:
    with (package_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["name"]


def load_dependencies(package_dir: Path) -> list[str]:
    with (package_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    dependencies = data["project"]["dependencies"]
    result = []
    for dependency in dependencies:
        match = NAME_PATTERN.match(dependency.strip())
        if match:
            result.append(match.group(0))
    return sorted(result)


def build_plugin_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for family in PLUGIN_FAMILIES:
        for package_dir in (PACKAGES_DIR / family).iterdir():
            if not package_dir.is_dir():
                continue
            if not (package_dir / "pyproject.toml").exists():
                continue
            distribution = project_name(package_dir)
            if distribution in index:
                raise RuntimeError(
                    f"Duplicate plugin distribution name {distribution!r} detected under packages/"
                    "calibration|explanation|visualization."
                )
            index[distribution] = family
    return index


def load_meta_dependencies() -> dict[str, list[str]]:
    meta_deps: dict[str, list[str]] = {}
    for package_dir in (PACKAGES_DIR / "meta").iterdir():
        if not package_dir.is_dir():
            continue
        if not (package_dir / "pyproject.toml").exists():
            continue
        distribution = project_name(package_dir)
        if distribution in meta_deps:
            raise RuntimeError(
                f"Duplicate metapackage distribution name {distribution!r} detected under packages/meta."
            )
        meta_deps[distribution] = load_dependencies(package_dir)
    return meta_deps


def main() -> int:
    plugin_index = build_plugin_index()
    meta_deps = load_meta_dependencies()
    errors: list[str] = []

    # Family metapackages define the official plugin set.
    for family, family_meta in FAMILY_META_DISTRIBUTIONS.items():
        current = meta_deps.get(family_meta)
        if current is None:
            errors.append(f"Missing metapackage {family_meta!r} under packages/meta.")
            continue
        if not current:
            errors.append(f"{family_meta!r} must declare at least one plugin dependency.")
            continue
        for dependency in current:
            dep_family = plugin_index.get(dependency)
            if dep_family is None:
                errors.append(
                    f"{family_meta!r} depends on unknown plugin distribution {dependency!r}."
                )
            elif dep_family != family:
                errors.append(
                    f"{family_meta!r} depends on {dependency!r}, but that package lives in "
                    f"the {dep_family!r} family."
                )

    # Umbrella metapackage must only depend on family metapackages.
    umbrella_current = meta_deps.get(UMBRELLA_META_DISTRIBUTION)
    expected_umbrella = sorted(FAMILY_META_DISTRIBUTIONS.values())
    if umbrella_current is None:
        errors.append(f"Missing metapackage {UMBRELLA_META_DISTRIBUTION!r} under packages/meta.")
    elif umbrella_current != expected_umbrella:
        errors.append(
            f"{UMBRELLA_META_DISTRIBUTION!r} dependencies are stale. "
            f"Expected {expected_umbrella}, found {umbrella_current}."
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "Metapackage dependency sync passed. Official plugin set is defined by "
        "family metapackage dependencies."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
