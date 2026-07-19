from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from runtime_harness import validate_runtime

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DOCSTRING_FAIL_UNDER = 70.0


def read_distribution_name(package_path: Path) -> str:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    name = data.get("project", {}).get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{package_path} is missing project.name")
    return name


def read_plugin_family(package_path: Path) -> str:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    family = data.get("tool", {}).get("ce_plugin_repo", {}).get("family")
    if family not in {"calibration", "explanation", "visualization"}:
        raise RuntimeError(f"{package_path} is missing a supported tool.ce_plugin_repo.family")
    return str(family)


def read_import_name(package_path: Path) -> str:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    import_name = data.get("tool", {}).get("ce_plugin_repo", {}).get("import_name")
    if not isinstance(import_name, str) or not import_name:
        raise RuntimeError(f"{package_path} is missing tool.ce_plugin_repo.import_name")
    return import_name


def calibrated_explanations_requirement(package_path: Path) -> str:
    family = read_plugin_family(package_path)
    if family == "visualization":
        return "calibrated-explanations[viz]"
    return "calibrated-explanations"


def venv_python(venv_dir: Path) -> Path:
    candidate = venv_dir / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return venv_dir / "bin" / "python"


def find_wheel(package_path: Path, artifact_dir: Path) -> Path:
    distribution = read_distribution_name(package_path).replace("-", "_")
    wheels = sorted(artifact_dir.glob(f"{distribution}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one wheel for {package_path} in {artifact_dir}, found {len(wheels)}"
        )
    return wheels[0]


def build_wheel(package_path: Path, artifact_dir: Path) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(artifact_dir), str(package_path)]
    )
    return find_wheel(package_path, artifact_dir)


def create_virtualenv(venv_dir: Path) -> Path:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)
    return venv_python(venv_dir)


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.check_call(command, cwd=ROOT, env=env)


def plugin_docstring_coverage(package_path: Path) -> float:
    documented = 0
    total = 0
    for path in sorted((package_path / "src").rglob("plugin.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_plugin_meta = any(
                isinstance(child, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "plugin_meta"
                    for target in child.targets
                )
                for child in node.body
            )
            if not has_plugin_meta:
                continue
            total += 1
            if ast.get_docstring(node, clean=False):
                documented += 1
    if total == 0:
        return 100.0
    return documented / total * 100


def check_plugin_docstrings(package_path: Path) -> None:
    coverage = plugin_docstring_coverage(package_path)
    print(f"Plugin entry-point docstring coverage: {coverage:.1f}%")
    if coverage < PLUGIN_DOCSTRING_FAIL_UNDER:
        raise RuntimeError(
            f"{package_path} plugin.py docstring coverage is {coverage:.1f}%, "
            f"below {PLUGIN_DOCSTRING_FAIL_UNDER:.1f}%"
        )


def outer_check(package_path: Path, artifact_dir: Path | None, run_pytest: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="ce-plugin-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        dist_dir = artifact_dir.resolve() if artifact_dir else tmp_path / "dist"
        wheel_path = (
            find_wheel(package_path, dist_dir)
            if artifact_dir
            else build_wheel(package_path, dist_dir)
        )
        venv_dir = tmp_path / "venv"
        python_bin = create_virtualenv(venv_dir)

        # Ensure runtime validation exercises the released calibrated-explanations package from pip.
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                calibrated_explanations_requirement(package_path),
            ]
        )
        run_checked([str(python_bin), "-m", "pip", "install", str(wheel_path)])
        if run_pytest:
            run_checked([str(python_bin), "-m", "pip", "install", "pytest", "pytest-cov"])

        run_checked(
            [
                str(python_bin),
                str(Path(__file__).resolve()),
                "--installed",
                "--package-path",
                str(package_path),
                *([] if run_pytest else ["--skip-pytest"]),
            ]
        )


def installed_check(package_path: Path, run_pytest: bool) -> None:
    # `--installed` is used by metapackage checks; ensure calibrated-explanations
    # still comes from pip in that path as well.
    run_checked(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            calibrated_explanations_requirement(package_path),
        ]
    )
    if run_pytest:
        run_checked([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov"])
    # Declared dependency ranges must be mutually consistent in the gate venv.
    run_checked([sys.executable, "-m", "pip", "check"])
    validate_runtime(package_path)
    check_plugin_docstrings(package_path)
    if run_pytest:
        # Coverage targets the import name so the measured module is whatever
        # the tests import — the installed wheel in the gate venv (the tests'
        # conftest falls back to src/ only when no matching wheel is installed).
        run_checked(
            [
                sys.executable,
                "-m",
                "pytest",
                str(package_path / "tests"),
                f"--cov={read_import_name(package_path)}",
                "--cov-report=term-missing",
                "--cov-fail-under=80",
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a plugin package from its built wheel.")
    parser.add_argument("--package-path", required=True)
    parser.add_argument("--artifact-dir")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    package_path = Path(args.package_path).resolve()
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else None
    run_pytest = not args.skip_pytest

    if args.installed:
        installed_check(package_path, run_pytest)
    else:
        outer_check(package_path, artifact_dir, run_pytest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
