"""Policy checks against the real repository (acceptance 4, 18, 19, 20)."""

from __future__ import annotations

from check_docs_install_commands import main as docs_check_main
from policy_fixtures import FAMILY_META, UMBRELLA, make_plugin
from repo_packages import (
    load_package_records,
    requirement_name,
    validate_curation,
    validate_statuses,
)
from validate_repo_structure import validate_repository


def test_real_repository_passes_baseline_validation(repo_root):
    assert validate_repository(repo_root) == []


def test_real_repository_curation_and_statuses_are_clean(repo_root):
    records = load_package_records(repo_root)
    assert validate_statuses(records) == []
    assert validate_curation(records) == []


def test_umbrella_depends_only_on_family_metapackages(repo_root):
    records = load_package_records(repo_root)
    umbrella = next(r for r in records if r.distribution_name == UMBRELLA)
    dependency_names = sorted(
        requirement_name(dep) for dep in umbrella.dependencies
    )
    assert dependency_names == sorted(FAMILY_META.values())


def test_runtime_trust_metadata_is_independent_of_repository_status(repo_root, tmp_path):
    # Real repo: the calibration example ships trusted-plugin runtime metadata
    # yet remains experimental in the repository lifecycle.
    records = load_package_records(repo_root)
    example = next(
        r
        for r in records
        if r.distribution_name == "calibrated-explanations-calibration-example"
    )
    assert example.status == "experimental"
    assert not hasattr(example, "trusted")

    # Synthetic repo: plugin_meta trusted=True must not leak into lifecycle state.
    make_plugin(tmp_path, "calibration", "demo", status="experimental", trusted_meta=True)
    record = load_package_records(tmp_path)[0]
    assert record.status == "experimental"


def test_packages_remain_independently_versioned(repo_root):
    records = load_package_records(repo_root)
    versions = {r.distribution_name: r.version for r in records}
    # Independent versioning is preserved: packages do not share one version.
    assert versions["calibrated-explanations-visualization-plotly"] != versions[
        "calibrated-explanations-visualization-example"
    ]
    assert all(version.count(".") == 2 for version in versions.values())


def test_docs_do_not_advertise_pypi_installs_for_unpublished_plugins(repo_root, capsys):
    assert docs_check_main() == 0
    assert "passed" in capsys.readouterr().out


def test_no_plugin_is_silently_mature(repo_root):
    # The migration classified every existing plugin as experimental; mature
    # status may only appear through a reviewed promotion PR that also updates
    # docs/lifecycle-migration.md.
    records = load_package_records(repo_root)
    plugins = [r for r in records if r.package_type == "plugin"]
    migration_doc = (repo_root / "docs" / "lifecycle-migration.md").read_text(
        encoding="utf-8"
    )
    for plugin in plugins:
        if plugin.status != "experimental":
            assert plugin.maintainers, (
                f"{plugin.distribution_name} is {plugin.status} but has no named maintainer"
            )
            assert plugin.distribution_name in migration_doc
