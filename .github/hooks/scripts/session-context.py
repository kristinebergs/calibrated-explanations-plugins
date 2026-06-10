#!/usr/bin/env python3
"""
SessionStart context injection hook for calibrated-explanations-plugins.
Injects plugin repo context and CE version into every agent session.
Non-blocking — exits 0 regardless.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OSS_PYPROJECT = REPO_ROOT / "calibrated_explanations" / "pyproject.toml"
PLUGINS_AGENTS = REPO_ROOT / "calibrated-explanations-plugins" / "AGENTS.md"


def _read_ce_version() -> str:
    try:
        if not OSS_PYPROJECT.exists():
            return "unknown (calibrated_explanations not found at ../)"
        text = OSS_PYPROJECT.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


def _count_packages() -> int:
    packages_dir = REPO_ROOT / "calibrated-explanations-plugins" / "packages"
    if not packages_dir.exists():
        return 0
    return sum(1 for p in packages_dir.rglob("pyproject.toml"))


def main() -> int:
    ce_version = _read_ce_version()
    pkg_count = _count_packages()

    parts = [
        "🔌 calibrated-explanations-plugins workspace",
        f"   CE upstream version: {ce_version}",
        f"   Plugin packages: {pkg_count}",
        "",
        "📋 Rules: extend Protocol classes only — no base class subclassing",
        "🔗 Plugin ADRs: ADR-006, ADR-013, ADR-014, ADR-015 (in calibrated_explanations/docs/)",
        "🚀 Release order: OSS → enterprise → plugins (coordinate via @release-coordinator)",
    ]

    output = {"systemMessage": "\n".join(parts)}
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
