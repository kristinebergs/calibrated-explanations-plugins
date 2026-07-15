"""Validate package references and install claims in repository docs.

Every package must be discoverable in the docs, and the docs must not
advertise a plain PyPI install command for a plugin that is not mature.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import ROOT, load_package_records  # noqa: E402

DOC_PATHS = [
    ROOT / "README.md",
    ROOT / "docs" / "which-package-should-i-install.md",
    ROOT / "docs" / "package-index.md",
    ROOT / "docs" / "plugin-lifecycle.md",
]


def main() -> int:
    errors: list[str] = []
    records = load_package_records()
    docs = [(path, path.read_text(encoding="utf-8")) for path in DOC_PATHS if path.exists()]
    combined = "\n".join(text for _, text in docs)

    for record in records:
        if record.distribution_name not in combined:
            errors.append(
                f"package {record.distribution_name!r} is not referenced in repository docs"
            )
        if record.package_type == "plugin" and record.status != "mature":
            command = f"pip install {record.distribution_name}"
            for path, text in docs:
                if any(line.strip() == command for line in text.splitlines()):
                    errors.append(
                        f"{path.relative_to(ROOT)} advertises {command!r}, but "
                        f"{record.distribution_name!r} has status {record.status!r} "
                        "and is not published to PyPI"
                    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Documentation install command check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
