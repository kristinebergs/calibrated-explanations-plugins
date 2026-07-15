"""Status declaration and status-sensitive README validation (acceptance 1, 2, 4, 13, 14)."""

from __future__ import annotations

from policy_fixtures import (
    experimental_readme,
    make_full_meta_set,
    make_meta,
    make_plugin,
    mature_readme,
)
from validate_repo_structure import validate_repository


def test_plugin_without_status_fails_validation(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status=None, status_line="")
    errors = validate_repository(tmp_path)
    assert any("missing tool.ce_plugin_repo.status" in error for error in errors)


def test_unknown_status_fails_validation(tmp_path):
    make_plugin(
        tmp_path,
        "calibration",
        "demo",
        status_line='status = "candidate"',
        readme=experimental_readme("calibrated-explanations-calibration-demo", "calibration"),
    )
    errors = validate_repository(tmp_path)
    assert any("unknown status 'candidate'" in error for error in errors)
    assert any("experimental, mature, deprecated" in error for error in errors)


def test_experimental_plugin_passes_baseline_validation(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="experimental")
    make_full_meta_set(tmp_path)
    errors = validate_repository(tmp_path)
    assert errors == []


def test_metapackage_with_status_is_rejected(tmp_path):
    make_meta(
        tmp_path,
        "calibrated-explanations-calibration",
        [],
        status_line='status = "mature"',
    )
    errors = validate_repository(tmp_path)
    assert any("must not declare" in error and "status" in error for error in errors)


def test_experimental_readme_must_not_advertise_pypi_install(tmp_path):
    dist = "calibrated-explanations-calibration-demo"
    bad_readme = experimental_readme(dist, "calibration").replace(
        f"pip install ./packages/calibration/{dist}",
        f"pip install {dist}",
    )
    make_plugin(tmp_path, "calibration", "demo", readme=bad_readme)
    errors = validate_repository(tmp_path)
    assert any("must not advertise" in error for error in errors)
    assert any("must document a source install" in error for error in errors)


def test_experimental_readme_requires_not_published_warning(tmp_path):
    dist = "calibrated-explanations-calibration-demo"
    bad_readme = experimental_readme(dist, "calibration").replace(
        "not published to PyPI", "still being evaluated"
    )
    make_plugin(tmp_path, "calibration", "demo", readme=bad_readme)
    errors = validate_repository(tmp_path)
    assert any("'not published to PyPI'" in error for error in errors)


def test_mature_readme_requires_pypi_install_command(tmp_path):
    dist = "calibrated-explanations-calibration-demo"
    bad_readme = mature_readme(dist, "calibration").replace(
        f"pip install {dist}", "pip install ./somewhere"
    )
    make_plugin(tmp_path, "calibration", "demo", status="mature", readme=bad_readme)
    errors = validate_repository(tmp_path)
    assert any(f"'pip install {dist}'" in error for error in errors)


def test_mature_readme_with_pypi_install_passes(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    errors = validate_repository(tmp_path)
    assert errors == []


def test_mature_plugin_requires_maintainer_and_licence(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature", mature_metadata=False)
    errors = validate_repository(tmp_path)
    assert any("project.maintainers" in error for error in errors)
    assert any("project.license" in error for error in errors)


def test_experimental_description_must_not_claim_official(tmp_path):
    make_plugin(
        tmp_path,
        "calibration",
        "demo",
        description="Official calibration plugin for calibrated-explanations",
    )
    errors = validate_repository(tmp_path)
    assert any("must not describe itself as 'official'" in error for error in errors)


def test_deprecated_readme_requires_notice_and_migration(tmp_path):
    dist = "calibrated-explanations-calibration-demo"
    bad_readme = experimental_readme(dist, "calibration").replace(
        "Status: `experimental`", "Status: `deprecated`"
    )
    make_plugin(tmp_path, "calibration", "demo", status="deprecated", readme=bad_readme)
    errors = validate_repository(tmp_path)
    assert any("'**Deprecated**' notice" in error for error in errors)
    assert any("migration" in error for error in errors)
