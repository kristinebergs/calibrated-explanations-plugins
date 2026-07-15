"""Shared builders for synthetic lifecycle-policy test repositories."""

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


def experimental_readme(dist: str, family: str) -> str:
    return dedent(
        f"""\
        # {dist}

        Family: `{family}`

        Status: `experimental`

        > **Experimental**: this plugin has not completed a maturity review and is
        > not published to PyPI. Install from source (see below).

        Purpose: Test fixture plugin.

        Install (from a checkout):

        ```bash
        pip install ./packages/{family}/{dist}
        ```

        Compatibility: `calibrated-explanations>=0.11`
        """
    )


def mature_readme(dist: str, family: str) -> str:
    return dedent(
        f"""\
        # {dist}

        Family: `{family}`

        Status: `mature`

        Purpose: Test fixture plugin.

        Install:

        ```bash
        pip install {dist}
        ```

        Compatibility: `calibrated-explanations>=0.11`

        Support: open an issue in the plugin repository.

        Known limitations: none beyond the CE plugin contract.
        """
    )


def deprecated_readme(dist: str, family: str) -> str:
    return dedent(
        f"""\
        # {dist}

        Family: `{family}`

        Status: `deprecated`

        **Deprecated**: this plugin is no longer recommended.

        Migration: use `calibrated-explanations-{family}-other` instead.

        Purpose: Test fixture plugin.

        Compatibility: `calibrated-explanations>=0.11`
        """
    )


def make_plugin(
    root: Path,
    family: str,
    slug: str,
    *,
    status: str | None = "experimental",
    status_line: str | None = "__DEFAULT__",
    version: str = "0.1.0",
    requires_python: str = ">=3.11",
    mature_metadata: bool | None = None,
    readme: str | None = None,
    trusted_meta: bool = False,
    description: str | None = None,
) -> Path:
    """Create a structurally valid plugin package in a synthetic repo."""
    dist = f"calibrated-explanations-{family}-{slug}"
    import_name = f"ce_{family}_{slug}".replace("-", "_")
    package_dir = root / "packages" / family / dist
    src_dir = package_dir / "src" / import_name
    tests_dir = package_dir / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    if mature_metadata is None:
        mature_metadata = status == "mature"
    if status_line == "__DEFAULT__":
        status_line = f'status = "{status}"' if status is not None else ""
    if description is None:
        description = f"{family.capitalize()} plugin for calibrated-explanations"

    maintainers_block = (
        '\nmaintainers = [\n    { name = "Test Maintainer", email = "maint@example.org" },\n]\n'
        'license = "BSD-3-Clause"\n'
        if mature_metadata
        else ""
    )
    capability = {
        "calibration": "interval:classification",
        "explanation": "explanation:factual",
        "visualization": "plot:builder",
    }[family]
    entry_groups = f"""
[project.entry-points."calibrated_explanations.plugins"]
{slug} = "{import_name}.plugin:FixturePlugin"
"""
    if family == "visualization":
        entry_groups += f"""
[project.entry-points."calibrated_explanations.plugins.plot_builders"]
{slug} = "{import_name}.plugin:FixturePlugin"

[project.entry-points."calibrated_explanations.plugins.plot_renderers"]
{slug} = "{import_name}.plugin:FixturePlugin"
"""

    (package_dir / "pyproject.toml").write_text(
        dedent(
            f"""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "{dist}"
            version = "{version}"
            description = "{description}"
            readme = "README.md"
            requires-python = "{requires_python}"
            dependencies = [
                "calibrated-explanations>=0.11",
            ]
            """
        )
        + maintainers_block
        + entry_groups
        + dedent(
            f"""
            [tool.hatch.build.targets.wheel]
            packages = ["src/{import_name}"]

            [tool.ce_plugin_repo]
            family = "{family}"
            {status_line}
            import_name = "{import_name}"
            """
        ),
        encoding="utf-8",
    )

    if readme is None:
        if status == "mature":
            readme = mature_readme(dist, family)
        elif status == "deprecated":
            readme = deprecated_readme(dist, family)
        else:
            readme = experimental_readme(dist, family)
    (package_dir / "README.md").write_text(readme, encoding="utf-8")

    trusted_value = "True" if trusted_meta else "False"
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "plugin.py").write_text(
        dedent(
            f"""\
            class FixturePlugin:
                plugin_meta = {{
                    "schema_version": 1,
                    "name": "test.{family}.{slug}",
                    "version": "{version}",
                    "provider": "test",
                    "data_modalities": ("tabular",),
                    "capabilities": ["{capability}"],
                    "trusted": {trusted_value},
                }}
            """
        ),
        encoding="utf-8",
    )
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / f"test_{slug.replace('-', '_')}.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )
    return package_dir


def make_meta(
    root: Path,
    dist: str,
    dependencies: list[str],
    *,
    requires_python: str = ">=3.11",
    status_line: str = "",
) -> Path:
    package_dir = root / "packages" / "meta" / dist
    package_dir.mkdir(parents=True)
    dependency_lines = ",\n    ".join(f'"{dep}"' for dep in dependencies)
    (package_dir / "pyproject.toml").write_text(
        dedent(
            f"""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "{dist}"
            version = "0.1.0"
            description = "Curated metapackage for calibrated-explanations plugins"
            readme = "README.md"
            requires-python = "{requires_python}"
            dependencies = [
                {dependency_lines}
            ]

            [tool.hatch.build.targets.wheel]
            bypass-selection = true

            [tool.ce_plugin_repo]
            family = "meta"
            {status_line}
            """
        ),
        encoding="utf-8",
    )
    (package_dir / "README.md").write_text(
        dedent(
            f"""\
            # {dist}

            Family: `meta`

            Purpose: Test fixture metapackage.

            Install:

            ```bash
            pip install {dist}
            ```

            Compatibility: `calibrated-explanations>=0.11`
            """
        ),
        encoding="utf-8",
    )
    return package_dir


def make_full_meta_set(root: Path, family_deps: dict[str, list[str]] | None = None) -> None:
    family_deps = family_deps or {}
    for family, dist in FAMILY_META.items():
        make_meta(root, dist, family_deps.get(family, []))
    make_meta(root, UMBRELLA, sorted(FAMILY_META.values()))
