from __future__ import annotations

import importlib

import pytest


def _load_dashboard_cards(monkeypatch):
    return importlib.import_module("ce_visualization_plotly.dashboard_cards")


def test_dashboard_registry_contains_current_plotly_styles(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    descriptors = dashboard_cards.iter_dashboard_cards()

    assert [descriptor.card_id for descriptor in descriptors] == [
        "instance_explorer",
        "local_factual_bars",
        "local_factual_simple",
        "uncertainty_quadrant",
        "ensured",
        "alternative_feature_summary",
    ]
    assert {descriptor.style for descriptor in descriptors} == {
        "plotly.global.instance_explorer",
        "plotly.local.factual_bars",
        "plotly.local.factual_simple",
        "plotly.local.uncertainty_quadrant",
        "plotly.local.ensured",
        "plotly.local.alternative_feature_summary",
    }


def test_dashboard_registry_supports_lookup_by_id_and_style(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    ensured = dashboard_cards.find_dashboard_card("ensured")
    factual_bars = dashboard_cards.find_dashboard_card("local_factual_bars")

    assert ensured is not None
    assert ensured.style == "plotly.local.ensured"
    assert factual_bars is not None
    assert factual_bars.style == "plotly.local.factual_bars"
    assert factual_bars.default_options["show_uncertainty"] is False
    assert factual_bars.default_options["hover_uncertainty"] is True
    assert factual_bars.default_options["filter_top"] == 10
    assert dashboard_cards.find_dashboard_card_by_style("plotly.local.ensured") is ensured
    assert (
        dashboard_cards.find_dashboard_card_by_style("plotly.local.factual_bars")
        is factual_bars
    )
    assert dashboard_cards.find_dashboard_card("missing") is None
    assert dashboard_cards.find_dashboard_card_by_style("plotly.local.missing") is None


def test_dashboard_registry_filters_scope_and_task(monkeypatch):
    dashboard_cards = _load_dashboard_cards(monkeypatch)

    global_cards = dashboard_cards.dashboard_cards_for_scope("global")
    local_cards = dashboard_cards.dashboard_cards_for_scope("local")
    regression_cards = dashboard_cards.dashboard_cards_for_task("regression")

    assert [card.card_id for card in global_cards] == ["instance_explorer"]
    assert [card.card_id for card in local_cards] == [
        "local_factual_bars",
        "local_factual_simple",
        "uncertainty_quadrant",
        "ensured",
        "alternative_feature_summary",
    ]
    assert [card.card_id for card in regression_cards] == [
        "instance_explorer",
        "local_factual_bars",
        "local_factual_simple",
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
