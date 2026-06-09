"""Static checks for the mandatory IDR usage notebook."""

from __future__ import annotations

import json
import os
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "examples" / "idr_regression_calibrator.ipynb"


def test_example_notebook_exists_and_documents_lifecycles():
    """Ensure the notebook captures both valid lifecycles and the invalid double-fit pattern."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "WrapCalibratedExplainer" in text
    assert "explainer.fit(X_train, y_train)" in text
    assert "prefit_model = RandomForestRegressor(random_state=0).fit" in text
    assert "# explainer.fit(X_train, y_train)  # double-fit anti-pattern" in text
    assert "threshold=float(np.median(y_cal))" in text


def test_double_fit_pattern_is_not_executable_code():
    """Ensure the invalid double-fit example is documentation-only comments."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    executable_lines = [
        line.strip()
        for line in code.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    invalid_fit = "model = RandomForestRegressor(random_state=0).fit(X_train, y_train)"
    assert invalid_fit not in executable_lines
    assert "explainer.fit(X_train, y_train)  # double-fit anti-pattern" not in executable_lines


def test_execute_example_notebook_when_real_backend_required():
    """Execute the example notebook in the mandatory real-backend CI job."""
    if os.environ.get("CE_IDR_REQUIRE_REAL_BACKEND") != "1":
        return
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    globals_dict = {"__name__": "__idr_notebook_smoke__"}
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        exec(compile(source, str(NOTEBOOK), "exec"), globals_dict)  # noqa: S102  # nosec B102
