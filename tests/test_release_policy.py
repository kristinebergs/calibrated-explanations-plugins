"""Release gating: tag resolution, status eligibility, curation, ancestry."""

from __future__ import annotations

import subprocess

import pytest
from fixtures import FAMILY_META, UMBRELLA, write_meta_set, write_plugin
from lifecycle import ensure_reachable, gate_release, load_packages, meta_closure


def gate(root, name, version="0.1.0"):
    return gate_release(load_packages(root), f"pkg/{name}/v{version}", root)


def test_malformed_tag_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="pkg/<distribution>"):
        gate_release([], "v1.2.3", tmp_path)


def test_unknown_distribution_is_rejected(tmp_path):
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="No package"):
        gate(tmp_path, "calibrated-explanations-calibration-ghost")


def test_tag_version_must_match_package_version(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature", version="0.2.0")
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="does not match"):
        gate(tmp_path, dist, "0.1.0")


def test_experimental_plugin_cannot_be_released(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="experimental")
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="experimental"):
        gate(tmp_path, dist)


def test_deprecated_plugin_cannot_be_released(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="deprecated")
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="deprecated"):
        gate(tmp_path, dist)


def test_mature_plugin_with_required_metadata_is_releasable(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    write_meta_set(tmp_path)
    package = gate(tmp_path, dist)
    assert package.package_type == "plugin"


def test_mature_plugin_without_maintainer_is_blocked(tmp_path):
    dist = write_plugin(
        tmp_path, "calibration", "demo", status="mature", mature_metadata=False
    )
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="maintainers"):
        gate(tmp_path, dist)


def test_metapackage_release_blocked_by_curation_violation(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="experimental")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})
    with pytest.raises(SystemExit, match="experimental"):
        gate(tmp_path, FAMILY_META["calibration"])


def test_empty_family_metapackage_is_not_releasable(tmp_path):
    write_meta_set(tmp_path)
    with pytest.raises(SystemExit, match="empty"):
        gate(tmp_path, FAMILY_META["calibration"])


def test_umbrella_release_blocked_while_any_family_metapackage_is_empty(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    write_meta_set(tmp_path, {"calibration": [f"{dist}>=0.1,<1"]})  # other two empty
    with pytest.raises(SystemExit, match="empty"):
        gate(tmp_path, UMBRELLA)


def test_valid_metapackage_release_and_curated_closure(tmp_path):
    curated = {
        family: [f"{write_plugin(tmp_path, family, 'demo', status='mature')}>=0.1,<1"]
        for family in FAMILY_META
    }
    write_plugin(tmp_path, "calibration", "sandbox", status="experimental")
    write_meta_set(tmp_path, curated)

    packages = load_packages(tmp_path)
    family_meta = gate(tmp_path, FAMILY_META["calibration"])
    closure = {p.name for p in meta_closure(packages, family_meta)}
    assert closure == {
        FAMILY_META["calibration"],
        "calibrated-explanations-calibration-demo",
    }

    umbrella = gate(tmp_path, UMBRELLA)
    closure = {p.name for p in meta_closure(packages, umbrella)}
    assert "calibrated-explanations-calibration-sandbox" not in closure
    assert set(FAMILY_META.values()) <= closure


def test_extra_empty_metapackage_blocks_only_its_own_release(tmp_path):
    dist = write_plugin(tmp_path, "calibration", "demo", status="mature")
    write_meta_set(tmp_path)
    package = gate(tmp_path, dist)
    assert package.status == "mature"


def _git(cwd, *args):
    subprocess.check_call(
        ["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def test_released_commit_must_be_reachable_from_default_branch(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.org")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "on main")
    ensure_reachable("HEAD", "main", cwd=tmp_path)

    _git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "unmerged")
    with pytest.raises(SystemExit, match="not reachable"):
        ensure_reachable("HEAD", "main", cwd=tmp_path)
