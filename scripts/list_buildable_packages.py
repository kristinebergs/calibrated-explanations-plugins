"""List package directories as JSON, optionally filtered by type or status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import ALLOWED_STATUSES, ROOT, load_package_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="List package directories as JSON.")
    parser.add_argument(
        "--package-type", choices=("plugin", "meta"), help="Only list this package type."
    )
    parser.add_argument(
        "--status",
        choices=ALLOWED_STATUSES,
        help="Only list plugin packages with this lifecycle status.",
    )
    args = parser.parse_args()

    records = load_package_records()
    selected = []
    for record in records:
        if args.package_type and record.package_type != args.package_type:
            continue
        if args.status and record.status != args.status:
            continue
        selected.append(record.relative_path(ROOT))
    print(json.dumps(sorted(selected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
