"""Release gating (acceptance 5, 7, 11, 16)."""

from __future__ import annotations

import subprocess

import pytest
from policy_fixtures import make_full_meta_set, make_plugin
from repo_packages import load_package_records
from resolve_release_tag import ensure_reachable_from, parse_tag, resolve_package


def _resolve(root, dist, version, **kwargs):
    return resolve_package(load_package_records(root), dist, version, root=root, **kwargs)


def test_tag_parsing():
    assert parse_tag("pkg/calibrated-explanations-calibration-demo/v1.2.3") == (
        "calibrated-explanations-calibration-demo",
        "1.2.3",
    )
    with pytest.raises(SystemExit):
        parse_tag("v1.2.3")


def test_experimental_plugin_cannot_be_released(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="experimental")
    with pytest.raises(SystemExit, match="experimental"):
        _resolve(tmp_path, "calibrated-explanations-calibration-demo", "0.1.0")


def test_mature_plugin_resolves_for_release(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    package = _resolve(tmp_path, "calibrated-explanations-calibration-demo", "0.1.0")
    assert package.status == "mature"
    assert package.package_type == "plugin"


def test_deprecated_plugin_rejected_by_default(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="deprecated")
    with pytest.raises(SystemExit, match="deprecated"):
        _resolve(tmp_path, "calibrated-explanations-calibration-demo", "0.1.0")


def test_deprecated_plugin_released_only_with_explicit_override(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="deprecated")
    package = _resolve(
        tmp_path,
        "calibrated-explanations-calibration-demo",
        "0.1.0",
        allow_deprecated=True,
    )
    assert package.status == "deprecated"


def test_version_mismatch_is_rejected(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature", version="0.2.0")
    with pytest.raises(SystemExit, match="does not match"):
        _resolve(tmp_path, "calibrated-explanations-calibration-demo", "0.1.0")


def test_metapackage_release_rejected_when_curation_fails(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="experimental")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    with pytest.raises(SystemExit, match="curation invariants"):
        _resolve(tmp_path, "calibrated-explanations-calibration", "0.1.0")


def test_metapackage_release_resolves_when_curation_clean(tmp_path):
    make_plugin(tmp_path, "calibration", "demo", status="mature")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-demo>=0.1,<1"]},
    )
    package = _resolve(tmp_path, "calibrated-explanations-calibration", "0.1.0")
    assert package.package_type == "meta"


def _git(cwd, *args):
    subprocess.check_call(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_release_commit_must_be_reachable_from_default_branch(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.org")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "on main")
    ensure_reachable_from("HEAD", "main", cwd=tmp_path)

    _git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "unmerged")
    with pytest.raises(SystemExit, match="not reachable"):
        ensure_reachable_from("HEAD", "main", cwd=tmp_path)
