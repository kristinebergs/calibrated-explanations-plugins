"""Minimal pyproject.toml builders for synthetic lifecycle-test repositories."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[1]
FAMILY_META = {
    "calibration": "calibrated-explanations-calibration",
    "explanation": "calibrated-explanations-explanation",
    "visualization": "calibrated-explanations-visualization",
}
UMBRELLA = "calibrated-explanations-plugins"


def write_plugin(
    root: Path,
    family: str,
    slug: str,
    *,
    status: str | None = "experimental",
    version: str = "0.1.0",
    directory_family: str | None = None,
    mature_metadata: bool | None = None,
) -> str:
    """Write a plugin pyproject.toml; returns the distribution name."""
    dist = f"calibrated-explanations-{family}-{slug}"
    if mature_metadata is None:
        mature_metadata = status == "mature"
    status_line = f'status = "{status}"' if status is not None else ""
    maintainers = (
        'maintainers = [{ name = "Test Maintainer", email = "m@example.org" }]\n'
        'license = "BSD-3-Clause"\n'
        if mature_metadata
        else ""
    )
    package_dir = root / "packages" / (directory_family or family) / dist
    package_dir.mkdir(parents=True)
    (package_dir / "pyproject.toml").write_text(
        dedent(
            f"""\
            [project]
            name = "{dist}"
            version = "{version}"
            dependencies = ["calibrated-explanations>=0.11"]
            """
        )
        + maintainers
        + dedent(
            f"""\
            [tool.ce_plugin_repo]
            family = "{family}"
            {status_line}
            import_name = "ce_{family}_{slug}"
            """
        ),
        encoding="utf-8",
    )
    return dist


def write_meta(root: Path, dist: str, dependencies: list[str], *, extra: str = "") -> None:
    package_dir = root / "packages" / "meta" / dist
    package_dir.mkdir(parents=True)
    dependency_lines = ", ".join(f'"{dep}"' for dep in dependencies)
    (package_dir / "pyproject.toml").write_text(
        dedent(
            f"""\
            [project]
            name = "{dist}"
            version = "0.1.0"
            dependencies = [{dependency_lines}]

            [tool.ce_plugin_repo]
            family = "meta"
            {extra}
            """
        ),
        encoding="utf-8",
    )


def write_meta_set(root: Path, family_deps: dict[str, list[str]] | None = None) -> None:
    """Write the three family metapackages plus the umbrella."""
    family_deps = family_deps or {}
    for family, dist in FAMILY_META.items():
        write_meta(root, dist, family_deps.get(family, []))
    write_meta(root, UMBRELLA, sorted(FAMILY_META.values()))
