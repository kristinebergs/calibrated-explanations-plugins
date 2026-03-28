from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def read_version(path: Path, ref: str | None) -> str | None:
    rel_path = path.relative_to(ROOT).as_posix()
    if ref is None:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
    else:
        try:
            raw = subprocess.check_output(["git", "show", f"{ref}:{rel_path}"], cwd=ROOT, text=True)
        except subprocess.CalledProcessError:
            return None
    data = tomllib.loads(raw)
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Require version bumps for changed packages.")
    parser.add_argument("--base", required=True)
    parser.add_argument("packages", nargs="*")
    args = parser.parse_args()

    errors: list[str] = []
    for package in args.packages:
        package_path = ROOT / package
        pyproject_path = package_path / "pyproject.toml"
        old_version = read_version(pyproject_path, args.base)
        new_version = read_version(pyproject_path, None)
        if old_version is None or new_version is None:
            continue
        changed_files = git("diff", "--name-only", args.base, "HEAD", "--", package).splitlines()
        material_changes = [
            file_path
            for file_path in changed_files
            if not file_path.endswith(".md") or file_path.endswith("pyproject.toml")
        ]
        if material_changes and old_version == new_version:
            errors.append(
                f"{package} changed materially but version stayed at {new_version}. "
                "Bump project.version in that package's pyproject.toml."
            )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Version bump check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
