from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="List changed package directories as JSON.")
    parser.add_argument("--base", default="")
    args = parser.parse_args()
    base = args.base or detect_base()
    changed = git("diff", "--name-only", base, "HEAD")
    packages: list[str] = []
    seen: set[str] = set()
    for line in changed.splitlines():
        path = Path(line)
        try:
            package_root = Path(*path.parts[:3])
        except IndexError:
            continue
        if len(path.parts) >= 3 and path.parts[0] == "packages":
            normalized = package_root.as_posix()
            if normalized not in seen:
                seen.add(normalized)
                packages.append(normalized)
    print(json.dumps(packages))
    return 0


def detect_base() -> str:
    for candidate in ("origin/main", "origin/master", "HEAD^"):
        try:
            git("rev-parse", "--verify", candidate)
            return candidate
        except subprocess.CalledProcessError:
            continue
    return "HEAD"


if __name__ == "__main__":
    raise SystemExit(main())
