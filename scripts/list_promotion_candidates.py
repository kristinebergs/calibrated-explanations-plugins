"""List packages whose lifecycle status changed to ``mature`` since a base ref.

Used by CI to force the complete mature-package validation suite on
maturity-promotion pull requests, regardless of ordinary changed-package
optimisations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import ROOT, load_package_records  # noqa: E402


def status_at_ref(base: str, rel_pyproject: str, *, cwd: Path) -> str | None:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{base}:{rel_pyproject}"],
            cwd=cwd,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None  # package did not exist at base
    data = tomllib.loads(raw)
    status = data.get("tool", {}).get("ce_plugin_repo", {}).get("status")
    return status if isinstance(status, str) else None


def promotion_candidates(base: str, root: Path = ROOT) -> list[str]:
    candidates: list[str] = []
    for record in load_package_records(root):
        if record.package_type != "plugin" or record.status != "mature":
            continue
        rel_pyproject = f"{record.relative_path(root)}/pyproject.toml"
        previous = status_at_ref(base, rel_pyproject, cwd=root)
        if previous != "mature":
            candidates.append(record.relative_path(root))
    return sorted(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List packages promoted to mature since the base ref, as JSON."
    )
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    print(json.dumps(promotion_candidates(args.base)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
