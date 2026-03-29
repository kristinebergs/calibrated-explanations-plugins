from __future__ import annotations

import argparse
import subprocess
import tempfile
import venv
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from official_plugins import official_plugin_paths_for_meta_distribution

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


def package_plugin_paths(meta_package_path: Path) -> list[Path]:
    distribution_name = read_distribution_name(meta_package_path)
    return official_plugin_paths_for_meta_distribution(distribution_name)


def find_wheel(package_path: Path, artifact_dir: Path) -> Path:
    distribution = read_distribution_name(package_path).replace("-", "_")
    wheels = sorted(artifact_dir.glob(f"{distribution}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one wheel for {package_path} in {artifact_dir}, found {len(wheels)}"
        )
    return wheels[0]


def create_virtualenv(venv_dir: Path) -> Path:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)
    return venv_python(venv_dir)


def run_checked(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate metapackage runtime coverage via local wheelhouse.")
    parser.add_argument("--package-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--wheelhouse", required=True)
    args = parser.parse_args()

    package_path = Path(args.package_path).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    wheelhouse = Path(args.wheelhouse).resolve()
    package_wheel = find_wheel(package_path, artifact_dir)
    plugin_paths = package_plugin_paths(package_path)

    with tempfile.TemporaryDirectory(prefix="ce-meta-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        python_bin = create_virtualenv(tmp_path / "venv")
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "calibrated-explanations[viz]",
            ]
        )
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                str(package_wheel),
            ]
        )
        for plugin_path in plugin_paths:
            run_checked(
                [
                    str(python_bin),
                    str(ROOT / "scripts" / "runtime_check_package.py"),
                    "--installed",
                    "--skip-pytest",
                    "--package-path",
                    str(plugin_path),
                ]
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
