"""Generated package index accuracy (acceptance 17)."""

from __future__ import annotations

from generate_package_index import render_index
from policy_fixtures import make_full_meta_set, make_plugin
from repo_packages import load_package_records


def _section(text: str, heading: str) -> str:
    parts = text.split(f"## {heading}\n")
    assert len(parts) == 2, f"missing section {heading!r}"
    return parts[1].split("## ")[0]


def test_index_reflects_status_and_curation(tmp_path):
    make_plugin(tmp_path, "calibration", "curated", status="mature")
    make_plugin(tmp_path, "calibration", "standalone", status="mature")
    make_plugin(tmp_path, "explanation", "sandbox", status="experimental")
    make_plugin(tmp_path, "visualization", "legacy", status="deprecated")
    make_full_meta_set(
        tmp_path,
        {"calibration": ["calibrated-explanations-calibration-curated>=0.1,<1"]},
    )

    index = render_index(load_package_records(tmp_path), tmp_path)

    curated = _section(index, "Mature curated plugins")
    assert "calibrated-explanations-calibration-curated" in curated
    assert "calibrated-explanations-calibration-standalone" not in curated

    standalone = _section(index, "Mature standalone plugins")
    assert "calibrated-explanations-calibration-standalone" in standalone

    experimental = _section(index, "Experimental plugins")
    assert "calibrated-explanations-explanation-sandbox" in experimental
    assert "Not published to PyPI" in experimental
    assert "pip install calibrated-explanations-explanation-sandbox" not in index

    deprecated = _section(index, "Deprecated plugins")
    assert "calibrated-explanations-visualization-legacy" in deprecated

    metas = _section(index, "Metapackages")
    assert "calibrated-explanations-plugins" in metas


def test_index_never_claims_pypi_for_experimental(tmp_path):
    make_plugin(tmp_path, "calibration", "sandbox", status="experimental")
    make_full_meta_set(tmp_path)
    index = render_index(load_package_records(tmp_path), tmp_path)
    experimental = _section(index, "Experimental plugins")
    assert "Not published to PyPI" in experimental
    assert "pip install calibrated-explanations-calibration-sandbox" not in index
