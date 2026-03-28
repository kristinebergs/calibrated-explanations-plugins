from __future__ import annotations

import argparse
import os
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


def read_distribution_name(package_path: Path) -> str:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    name = data.get("project", {}).get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{package_path} is missing project.name")
    return name


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
    subprocess.check_call([sys.executable, "-m", "build", "--wheel", "--outdir", str(artifact_dir), str(package_path)])
    return find_wheel(package_path, artifact_dir)


def create_virtualenv(venv_dir: Path) -> Path:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)
    return venv_python(venv_dir)


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.check_call(command, cwd=ROOT, env=env)


def outer_check(package_path: Path, artifact_dir: Path | None, run_pytest: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="ce-plugin-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        dist_dir = artifact_dir.resolve() if artifact_dir else tmp_path / "dist"
        wheel_path = find_wheel(package_path, dist_dir) if artifact_dir else build_wheel(package_path, dist_dir)
        venv_dir = tmp_path / "venv"
        python_bin = create_virtualenv(venv_dir)

        run_checked([str(python_bin), "-m", "pip", "install", str(wheel_path)])
        if run_pytest:
            run_checked([str(python_bin), "-m", "pip", "install", "pytest"])

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
    validate_runtime(package_path)
    if run_pytest:
        run_checked([sys.executable, "-m", "pytest", str(package_path / "tests")])


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
