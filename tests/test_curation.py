"""Metapackage curation invariants (acceptance 6, 8, 9, 10, 15, 18)."""

from __future__ import annotations

from policy_fixtures import FAMILY_META, UMBRELLA, make_full_meta_set, make_meta, make_plugin
from repo_packages import load_package_records, validate_curation


def _curation_errors(root):
    return validate_curation(load_package_records(root))


def test_experimental_plugin_cannot_be_referenced_by_metapackage(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="experimental")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    errors = _curation_errors(tmp_path)
    assert any("'experimental'" in error and "mature" in error.lower() for error in errors)


def test_deprecated_plugin_cannot_enter_metapackage(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="deprecated")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    errors = _curation_errors(tmp_path)
    assert any("'deprecated'" in error for error in errors)


def test_mature_curated_plugin_passes(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    assert _curation_errors(tmp_path) == []


def test_mature_standalone_plugin_needs_no_metapackage(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    make_full_meta_set(tmp_path)  # empty curation everywhere
    assert _curation_errors(tmp_path) == []
    records = load_package_records(tmp_path)
    plugin = next(r for r in records if r.package_type == "plugin")
    assert plugin.status == "mature"
    assert not plugin.in_metapackage


def test_wrong_family_plugin_cannot_enter_family_metapackage(tmp_path):
    make_plugin(tmp_path, "explanation", "demo", status="mature")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-explanation-demo>=0.1,<1"]},
    )
    errors = _curation_errors(tmp_path)
    assert any("belongs to the 'explanation' family" in error for error in errors)


def test_unknown_dependency_is_rejected(tmp_path):
    make_full_meta_set(tmp_path, {"calibration": ["numpy>=1.24"]})
    errors = _curation_errors(tmp_path)
    assert any("not a plugin package in this repository" in error for error in errors)


def test_incompatible_python_range_is_detected(tmp_path):
    make_plugin(
        tmp_path,
        "calibration",
        "demo",
        status="mature",
        requires_python=">=3.13",
    )
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    errors = _curation_errors(tmp_path)
    assert any("requires-python" in error and "3.11" in error for error in errors)


def test_umbrella_must_depend_only_on_family_metapackages(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    for dist in FAMILY_META.values():
        make_meta(tmp_path, dist, [])
    make_meta(
        tmp_path,
        UMBRELLA,
        [*sorted(FAMILY_META.values()), "calibrated-explanations-calibration-demo"],
    )
    errors = _curation_errors(tmp_path)
    assert any("must depend on exactly the family metapackages" in error for error in errors)


def test_umbrella_with_exact_family_dependencies_passes(tmp_path):
    make_full_meta_set(tmp_path)
    assert _curation_errors(tmp_path) == []
