"""Test import-path policy: prefer the installed distribution, fall back to src.

Release-grade runs (the wheel gate in ``scripts/runtime_check_package.py``)
install the built wheel into a clean venv and then run this test suite; in
that environment the installed distribution version matches ``pyproject.toml``
and the tests import the *installed* package — no source-tree shortcut.

In a development checkout the package is often not installed (or a stale
version is), so ``src/`` is prepended to ``sys.path`` only when the installed
distribution is absent or its version differs from ``pyproject.toml``.
"""

from __future__ import annotations

import sys
import tomllib
from importlib import metadata
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = _PACKAGE_DIR / "src"
_DISTRIBUTION = "calibrated-explanations-visualization-plotly"


def _pyproject_version() -> str | None:
    try:
        with (_PACKAGE_DIR / "pyproject.toml").open("rb") as handle:
            return tomllib.load(handle).get("project", {}).get("version")
    except OSError:
        return None


def _installed_version() -> str | None:
    try:
        return metadata.version(_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return None


#: True when tests import from the source tree instead of an installed wheel.
SRC_FALLBACK_ACTIVE = _installed_version() != _pyproject_version()

if SRC_FALLBACK_ACTIVE:
    sys.path.insert(0, str(SRC_DIR))
