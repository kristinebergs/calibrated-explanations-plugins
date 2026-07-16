"""Path setup for lifecycle policy tests (fixture builders live in fixtures.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
