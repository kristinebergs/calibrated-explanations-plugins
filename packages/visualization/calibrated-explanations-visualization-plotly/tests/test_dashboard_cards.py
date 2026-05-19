from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _load_dashboard_cards(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src))
    return importlib.import_module("ce_visualization_plotly.dashboard_cards")


def test_dashboard_registry_contains_current_plotly_styles(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    descriptors = dashboard_cards.iter_dashboard_cards()

    assert [descriptor.card_id for descriptor in descriptors] == [
        "instance_explorer",
        "uncertainty_quadrant",
        "ensured",
        "alternative_feature_summary",
    ]
    assert {descriptor.style for descriptor in descriptors} == {
        "plotly.global.instance_explorer",
        "plotly.local.uncertainty_quadrant",
        "plotly.local.ensured",
        "plotly.local.alternative_feature_summary",
    }


def test_dashboard_registry_supports_lookup_by_id_and_style(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    ensured = dashboard_cards.find_dashboard_card("ensured")

    assert ensured is not None
    assert ensured.style == "plotly.local.ensured"
    assert dashboard_cards.find_dashboard_card_by_style("plotly.local.ensured") is ensured
    assert dashboard_cards.find_dashboard_card("missing") is None
    assert dashboard_cards.find_dashboard_card_by_style("plotly.local.missing") is None


def test_dashboard_registry_filters_scope_and_task(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    global_cards = dashboard_cards.dashboard_cards_for_scope("global")
    local_cards = dashboard_cards.dashboard_cards_for_scope("local")
    regression_cards = dashboard_cards.dashboard_cards_for_task("regression")

    assert [card.card_id for card in global_cards] == ["instance_explorer"]
    assert [card.card_id for card in local_cards] == [
        "uncertainty_quadrant",
        "ensured",
        "alternative_feature_summary",
    ]
    assert [card.card_id for card in regression_cards] == [
        "instance_explorer",
        "uncertainty_quadrant",
        "ensured",
        "alternative_feature_summary",
    ]


def test_dashboard_card_descriptors_are_immutable(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)
    descriptor = dashboard_cards.find_dashboard_card("instance_explorer")

    assert descriptor is not None
    with pytest.raises(Exception):
        descriptor.card_id = "changed"
    with pytest.raises(TypeError):
        descriptor.default_options["task"] = "regression"
