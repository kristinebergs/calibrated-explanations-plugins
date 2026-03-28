from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = [
    ROOT / "README.md",
    ROOT / "docs" / "which-package-should-i-install.md",
    ROOT / "docs" / "package-index.md",
]


def package_names() -> list[str]:
    result: list[str] = []
    for pyproject_path in (ROOT / "packages").glob("*/*/pyproject.toml"):
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
        result.append(data["project"]["name"])
    return sorted(result)


def main() -> int:
    doc_text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS if path.exists())
    missing = [name for name in package_names() if name not in doc_text]
    if missing:
        for name in missing:
            print(f"ERROR: package {name!r} is not referenced in repository docs", file=sys.stderr)
        return 1
    print("Documentation install command check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
