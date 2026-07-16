"""Lifecycle policy: statuses, family placement, curation, index, scaffolding."""

from __future__ import annotations

import subprocess
import sys

from fixtures import FAMILY_META, REPO_ROOT, UMBRELLA, write_meta, write_meta_set, write_plugin
from lifecycle import load_packages, render_index, validate

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def errors_for(root):
    return validate(load_packages(root))


def test_missing_status_fails(tmp_path):
    write_plugin(tmp_path, "calibration", "demo", status=None)
    write_meta_set(tmp_path)
    assert any("status" in error for error in errors_for(tmp_path))


def test_unknown_status_fails(tmp_path):
    write_plugin(tmp_path, "calibration", "demo", status="candidate")
    write_meta_set(tmp_path)
    assert any("'candidate'" in error for error in errors_for(tmp_path))


def test_metapackage_must_not_declare_status(tmp_path):
    write_plugin(tmp_path, "calibration", "demo")
    write_meta_set(tmp_path)
    write_meta(tmp_path, "calibrated-explanations-extra", [], extra='status = "mature"')
    assert any("must not declare a status" in error for error in errors_for(tmp_path))


def test_family_must_match_directory(tmp_path):
    write_plugin(tmp_path, "explanation", "demo", directory_family="calibration")
    write_meta_set(tmp_path)
    assert any("must match its directory" in error for error in errors_for(tmp_path))


def test_experimental_plugin_cannot_enter_metapackage(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="experimental")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})
    assert any("'experimental'" in error for error in errors_for(tmp_path))


def test_deprecated_plugin_cannot_enter_metapackage(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="deprecated")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})
    assert any("'deprecated'" in error for error in errors_for(tmp_path))


def test_wrong_family_mature_plugin_cannot_enter_metapackage(tmp_path):
    dist = write_plugin(tmp_path, "explanation", "demo", status="mature")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})
    assert any("own family" in error for error in errors_for(tmp_path))


def test_unknown_metapackage_dependency_is_rejected(tmp_path):
    write_meta_set(tmp_path, {"calibration": ["numpy>=1.24"]})
    assert any("not a plugin package" in error for error in errors_for(tmp_path))


def test_mature_plugin_requires_maintainer_and_licence(tmp_path):
    write_plugin(tmp_path, "calibration", "demo", status="mature", mature_metadata=False)
    write_meta_set(tmp_path)
    errors = errors_for(tmp_path)
    assert any("maintainers" in error for error in errors)
    assert any("licence" in error for error in errors)


def test_mature_standalone_plugin_is_valid(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    write_meta_set(tmp_path)  # empty curation everywhere
    assert errors_for(tmp_path) == []
    record = next(p for p in load_packages(tmp_path) if p.name == dist)
    assert record.curated_in == ()


def test_mature_curated_plugin_is_valid(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})
    assert errors_for(tmp_path) == []


def test_empty_family_metapackage_is_valid_in_repository(tmp_path):
    write_meta_set(tmp_path)
    assert errors_for(tmp_path) == []


def test_umbrella_must_depend_on_exactly_the_family_metapackages(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    for meta_name in FAMILY_META.values():
        write_meta(tmp_path, meta_name, [])
    write_meta(tmp_path, UMBRELLA, [*sorted(FAMILY_META.values()), dist])
    assert any("exactly the family metapackages" in error for error in errors_for(tmp_path))


def test_index_reflects_status_and_curation(tmp_path):
    curated = write_plugin(tmp_path, "calibration", "curated", status="mature")
    standalone = write_plugin(tmp_path, "calibration", "standalone", status="mature")
    sandbox = write_plugin(tmp_path, "explanation", "sandbox", status="experimental")
    legacy = write_plugin(tmp_path, "visualization", "legacy", status="deprecated")
    write_meta_set(tmp_path, {"calibration": [f"{curated}>=0.1,<1"]})

    index = render_index(load_packages(tmp_path), tmp_path)
    sections = {
        part.splitlines()[0]: part for part in index.split("## ")[1:]
    }
    assert curated in sections["Mature curated plugins"]
    assert curated not in sections["Mature standalone plugins"]
    assert standalone in sections["Mature standalone plugins"]
    assert sandbox in sections["Experimental plugins"]
    assert legacy in sections["Deprecated plugins"]
    assert UMBRELLA in sections["Metapackages"]


def test_scaffolded_plugin_defaults_to_experimental_and_mature_is_rejected():
    package_dir = (
        REPO_ROOT / "packages" / "calibration" / "calibrated-explanations-calibration-probe"
    )
    args = [
        sys.executable, str(REPO_ROOT / "scripts" / "scaffold_package.py"),
        "--family", "calibration", "--package-type", "plugin", "--slug", "probe",
        "--distribution-name", "calibrated-explanations-calibration-probe",
        "--ce-range", ">=0.11", "--import-name", "ce_calibration_probe",
        "--plugin-identifier", "test.calibration.probe",
        "--capability", "interval:classification",
    ]
    try:
        rejected = subprocess.run(
            [*args, "--status", "mature"], capture_output=True, text=True
        )
        assert rejected.returncode != 0
        assert not package_dir.exists()

        result = subprocess.run(args, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        data = tomllib.loads((package_dir / "pyproject.toml").read_text(encoding="utf-8"))
        assert data["tool"]["ce_plugin_repo"]["status"] == "experimental"
    finally:
        if package_dir.exists():
            import shutil

            shutil.rmtree(package_dir)


def test_real_repository_policy_is_clean(repo_root):
    from validate_repo_structure import validate_repository

    assert validate_repository(repo_root) == []
    assert validate(load_packages(repo_root)) == []
    index_path = repo_root / "docs" / "package-index.md"
    assert index_path.read_text(encoding="utf-8") == render_index(
        load_packages(repo_root), repo_root
    )
