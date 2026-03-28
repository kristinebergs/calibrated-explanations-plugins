from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"


def main() -> int:
    package_dirs = sorted(
        pyproject.parent.relative_to(ROOT).as_posix()
        for pyproject in PACKAGES_DIR.glob("*/*/pyproject.toml")
    )
    print(json.dumps(package_dirs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

