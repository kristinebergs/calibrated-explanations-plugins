"""Scaffolding defaults and promotion detection (acceptance 3, 12)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from list_promotion_candidates import promotion_candidates
from policy_fixtures import REPO_ROOT, make_plugin

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

SCAFFOLD = REPO_ROOT / "scripts" / "scaffold_package.py"


def _scaffold(cwd_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCAFFOLD),
            "--family",
            "calibration",
            "--package-type",
            "plugin",
            "--slug",
            "scaffold-probe",
            "--distribution-name",
            "calibrated-explanations-calibration-scaffold-probe",
            "--ce-range",
            ">=0.11",
            "--import-name",
            "ce_calibration_scaffold_probe",
            "--plugin-identifier",
            "test.calibration.scaffold_probe",
            "--capability",
            "interval:classification",
            *extra,
        ],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def scaffolded_package():
    package_dir = (
        REPO_ROOT
        / "packages"
        / "calibration"
        / "calibrated-explanations-calibration-scaffold-probe"
    )
    yield package_dir
    if package_dir.exists():
        import shutil

        shutil.rmtree(package_dir)


def test_newly_scaffolded_plugin_is_experimental(scaffolded_package):
    result = _scaffold(REPO_ROOT)
    assert result.returncode == 0, result.stderr
    data = tomllib.loads(
        (scaffolded_package / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert data["tool"]["ce_plugin_repo"]["status"] == "experimental"
    description = data["project"]["description"]
    assert "official" not in description.lower()
    readme = (scaffolded_package / "README.md").read_text(encoding="utf-8")
    assert "Status: `experimental`" in readme
    assert "not published to PyPI" in readme
    assert "pip install ./packages/calibration/" in readme
    assert not any(
        line.strip() == "pip install calibrated-explanations-calibration-scaffold-probe"
        for line in readme.splitlines()
    )


def test_direct_mature_scaffolding_is_rejected(scaffolded_package):
    result = _scaffold(REPO_ROOT, "--status", "mature")
    assert result.returncode != 0
    assert "maturity-review" in result.stderr
    assert not scaffolded_package.exists()


def _git(cwd, *args):
    subprocess.check_call(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_promotion_to_mature_is_detected_for_release_grade_validation(tmp_path):
    package_dir = make_plugin(tmp_path, "calibration", "demo", status="experimental")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.org")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "experimental baseline")

    assert promotion_candidates("HEAD", tmp_path) == []

    pyproject = package_dir / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'status = "experimental"', 'status = "mature"'
        ),
        encoding="utf-8",
    )
    assert promotion_candidates("HEAD", tmp_path) == [
        "packages/calibration/calibrated-explanations-calibration-demo"
    ]


def test_ci_wires_promotions_to_the_mature_suite():
    workflow = (REPO_ROOT / ".github" / "workflows" / "package-checks.yml").read_text(
        encoding="utf-8"
    )
    assert "list_promotion_candidates.py" in workflow
    assert "mature-package suite for promoted packages" in workflow
    # Promoted packages run the full runtime check (no --skip-pytest).
    promoted_step = workflow.split("mature-package suite for promoted packages")[1]
    assert "runtime_check_package.py" in promoted_step
