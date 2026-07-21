"""Curation semantics for the Plotly plugin in the visualization family.

Deterministic, PyPI/venv-independent checks that the declared package
metadata matches the curation decision: base installs the mature Plotly
plugin without extras, ``[live]`` delegates to the plugin's own ``[live]``
extra, both paths share the reviewed ``<0.4`` ceiling, Dash is never a direct
dependency of either metapackage, and the generated index/docs agree.
Installed-wheel behaviour (Dash presence/absence in a real environment, the
no-auto-trust-then-explicit-registration proof, and the live-dashboard
construction smoke test) is covered by ``scripts/runtime_check_metapackage.py``,
which the release workflow runs against real built wheels.
"""

from __future__ import annotations

from pathlib import Path

from lifecycle import load_packages, render_index
from packaging.requirements import Requirement

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
VISUALIZATION_META = REPO_ROOT / "packages" / "meta" / "calibrated-explanations-visualization"
UMBRELLA_META = REPO_ROOT / "packages" / "meta" / "calibrated-explanations-plugins"
PLOTLY_PLUGIN = (
    REPO_ROOT / "packages" / "visualization" / "calibrated-explanations-visualization-plotly"
)
PLOTLY_DIST = "calibrated-explanations-visualization-plotly"


def _pyproject(path: Path) -> dict:
    with (path / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _requirement(dependency: str) -> Requirement:
    return Requirement(dependency)


def _specifier_clauses(requirement: Requirement) -> set[str]:
    return {str(clause) for clause in requirement.specifier}


def test_visualization_family_base_depends_on_plotly_without_extras():
    data = _pyproject(VISUALIZATION_META)
    deps = data["project"]["dependencies"]
    matching = [_requirement(dep) for dep in deps if _requirement(dep).name == PLOTLY_DIST]
    assert len(matching) == 1, "base dependencies must list the Plotly plugin exactly once"
    requirement = matching[0]
    assert requirement.extras == set(), "base dependency must not request any extras"
    assert _specifier_clauses(requirement) == {">=0.3.5", "<0.4"}


def test_visualization_family_live_extra_delegates_to_plotly_live():
    data = _pyproject(VISUALIZATION_META)
    live_deps = data["project"]["optional-dependencies"]["live"]
    matching = [_requirement(dep) for dep in live_deps if _requirement(dep).name == PLOTLY_DIST]
    assert len(matching) == 1, "[live] extra must depend on the Plotly plugin exactly once"
    requirement = matching[0]
    assert requirement.extras == {"live"}, "[live] extra must request the plugin's own [live] extra"
    assert _specifier_clauses(requirement) == {">=0.3.5", "<0.4"}


def test_visualization_family_never_declares_dash_directly():
    data = _pyproject(VISUALIZATION_META)
    all_deps = list(data["project"]["dependencies"])
    for extra_deps in data["project"].get("optional-dependencies", {}).values():
        all_deps += extra_deps
    names = {_requirement(dep).name for dep in all_deps}
    assert "dash" not in names, "the family metapackage must never depend on dash directly"


def test_visualization_family_has_no_other_dependencies_or_extras():
    data = _pyproject(VISUALIZATION_META)
    dep_names = {_requirement(dep).name for dep in data["project"]["dependencies"]}
    assert dep_names == {PLOTLY_DIST}
    assert set(data["project"].get("optional-dependencies", {})) == {"live"}


def test_umbrella_visualization_bound_matches_curated_family_line():
    data = _pyproject(UMBRELLA_META)
    matching = [
        _requirement(dep)
        for dep in data["project"]["dependencies"]
        if _requirement(dep).name == "calibrated-explanations-visualization"
    ]
    assert len(matching) == 1
    assert _specifier_clauses(matching[0]) == {">=0.3", "<0.4"}


def test_umbrella_has_no_live_extra():
    data = _pyproject(UMBRELLA_META)
    assert "optional-dependencies" not in data["project"], (
        "the umbrella package must not add a [live] extra of its own"
    )


def test_plotly_plugin_status_is_mature():
    data = _pyproject(PLOTLY_PLUGIN)
    assert data["tool"]["ce_plugin_repo"]["status"] == "mature"


def test_plotly_plugin_declares_live_extra_owning_dash():
    data = _pyproject(PLOTLY_PLUGIN)
    live_deps = data["project"]["optional-dependencies"]["live"]
    dash_deps = [dep for dep in live_deps if _requirement(dep).name == "dash"]
    assert len(dash_deps) == 1, "the Plotly plugin's own [live] extra must own the dash dependency"


def test_generated_index_classifies_plotly_as_mature_curated_not_standalone():
    packages = load_packages(REPO_ROOT)
    rendered = render_index(packages, REPO_ROOT)
    sections = {part.splitlines()[0]: part for part in rendered.split("## ")[1:]}
    assert PLOTLY_DIST in sections["Mature curated plugins"]
    assert PLOTLY_DIST not in sections["Mature standalone plugins"]

    plotly_package = next(p for p in packages if p.name == PLOTLY_DIST)
    assert plotly_package.curated_in == ("calibrated-explanations-visualization",)


def test_package_index_on_disk_is_up_to_date():
    packages = load_packages(REPO_ROOT)
    index_path = REPO_ROOT / "docs" / "package-index.md"
    assert index_path.read_text(encoding="utf-8") == render_index(packages, REPO_ROOT)


def test_no_stale_empty_visualization_family_statements_remain():
    stale_fragments = (
        "curated set is currently empty",
        "curated set stays empty",
        "no mature visualization plugin",
        "still \"experimental\"",
        "does not exist yet",
        "unclaimed",
    )
    authoritative_files = (
        VISUALIZATION_META / "README.md",
        VISUALIZATION_META / "pyproject.toml",
        UMBRELLA_META / "README.md",
        UMBRELLA_META / "pyproject.toml",
        PLOTLY_PLUGIN / "README.md",
        PLOTLY_PLUGIN / "pyproject.toml",
        REPO_ROOT / "docs" / "package-index.md",
    )
    for path in authoritative_files:
        text = path.read_text(encoding="utf-8").lower()
        for fragment in stale_fragments:
            assert fragment not in text, f"{path.relative_to(REPO_ROOT)} still says {fragment!r}"
