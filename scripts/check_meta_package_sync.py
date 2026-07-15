"""Validate the metapackage curation invariants.

Family metapackage dependency lists are the authoritative curated plugin sets.
This entry point enforces (via :mod:`repo_packages`):

- family metapackages depend only on known plugins of their own family;
- only ``mature`` plugins may be curated;
- the umbrella metapackage depends on exactly the family metapackages;
- curated plugins do not contradict the metapackage requires-python range.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import (  # noqa: E402
    load_package_records,
    validate_curation,
    validate_statuses,
)


def main() -> int:
    errors: list[str] = []
    records = load_package_records(errors=errors)
    errors.extend(validate_statuses(records))
    errors.extend(validate_curation(records))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "Metapackage curation check passed. Curated plugin sets are defined by "
        "family metapackage dependencies and contain only mature plugins."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
