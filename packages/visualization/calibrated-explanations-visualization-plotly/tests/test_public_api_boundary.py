"""Static enforcement of the CE public-API boundary for runtime code.

Production code under ``src/ce_visualization_plotly`` may only import from a
narrow set of documented CE public façades. This guards against silent
regressions back to deep implementation modules
(``calibrated_explanations.core.*``, ``calibrated_explanations.utils.helper``,
``calibrated_explanations.explanations.explanation``) or private
(``_``-prefixed) CE symbols, both of which are unversioned CE internals that
can change or vanish without notice.

Test code is exempt: a narrowly scoped diagnostic
(``test_inline_fill_color_matches_ce_legacy_implementation_diagnostic`` in
``test_alternative_bars.py``) intentionally imports the private
``calibrated_explanations.viz.builders._legacy_get_fill_color`` purely as an
optional, skippable drift check -- it is never the required correctness
oracle (see ``test_fill_color_matches_golden_values`` for that) and is not
covered by this boundary test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_SRC_PACKAGE_DIR = _PACKAGE_DIR / "src" / "ce_visualization_plotly"

# Exact dotted module paths production code may import CE symbols from. Each
# entry is a documented public façade (ADR-006/ADR-013/ADR-014 for the
# plugins.* modules; CE's own v1 upgrade checklist names utils.exceptions as
# the canonical exception import path; utils/viz/explanations re-export their
# public symbols at the package level).
_ALLOWED_CE_MODULES = frozenset(
    {
        "calibrated_explanations",
        "calibrated_explanations.explanations",
        "calibrated_explanations.plugins.plots",
        "calibrated_explanations.plugins.registry",
        "calibrated_explanations.utils",
        "calibrated_explanations.utils.exceptions",
        "calibrated_explanations.viz",
    }
)

# Explicitly named in the promotion audit as forbidden regardless of the
# allowlist above, so a violation is reported with a specific message rather
# than just "not in the allowlist".
_EXPLICITLY_FORBIDDEN_PREFIXES = (
    "calibrated_explanations.core",
    "calibrated_explanations.explanations.explanation",
    "calibrated_explanations.utils.helper",
)


def _iter_ce_imports(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            "calibrated_explanations"
        ):
            yield node.lineno, node.module, [alias.name for alias in node.names]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("calibrated_explanations"):
                    yield node.lineno, alias.name, []


def test_production_code_only_imports_public_ce_facades():
    """Every CE import in src/ must target an explicitly allowed façade
    module and must not bind a private (``_``-prefixed) CE symbol."""
    violations: list[str] = []

    for path in sorted(_SRC_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, module, names in _iter_ce_imports(tree):
            location = f"{path.name}:{lineno}"

            for forbidden in _EXPLICITLY_FORBIDDEN_PREFIXES:
                if module == forbidden or module.startswith(forbidden + "."):
                    violations.append(
                        f"{location}: '{module}' is an explicitly forbidden "
                        "deep-import path; use a documented public façade instead"
                    )

            if module not in _ALLOWED_CE_MODULES:
                violations.append(
                    f"{location}: '{module}' is not in the allowed CE façade "
                    f"list {sorted(_ALLOWED_CE_MODULES)}"
                )

            for name in names:
                if name.startswith("_"):
                    violations.append(
                        f"{location}: imports private CE symbol '{name}' from "
                        f"'{module}'"
                    )

    assert not violations, "CE public-API boundary violations:\n" + "\n".join(violations)


def test_production_code_never_imports_calibrated_explanations_core():
    """Belt-and-suspenders: no production file may import anything from
    ``calibrated_explanations.core`` (the private implementation package),
    even indirectly through a multi-target import statement."""
    offenders = []
    for path in sorted(_SRC_PACKAGE_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "calibrated_explanations.core" in text:
            offenders.append(path.name)
    assert not offenders, f"forbidden calibrated_explanations.core reference in: {offenders}"


_CAUSAL_LANGUAGE_PATTERN = re.compile(
    r"\bcauses?\b|\bcaused by\b|\bleads? to\b|\bdue to\b|\bresults? in\b", re.IGNORECASE
)


def test_no_source_string_implies_causal_interpretation():
    """Predictive movements (e.g. alternative-rule arrows) are explicitly
    documented as predictive, not causal (README "Interpretation"). This
    statically guards against a label, caption, or hover template
    regressing into causal language anywhere in runtime source."""
    offenders = []
    for path in sorted(_SRC_PACKAGE_DIR.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _CAUSAL_LANGUAGE_PATTERN.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "causal-implying language found in source:\n" + "\n".join(offenders)
