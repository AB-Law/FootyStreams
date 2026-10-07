"""Tests for ratings, profiles and market value."""

from __future__ import annotations

import pytest

from footystreams.domain.profile import build_profile
from footystreams.domain.ratings import compute_current_ability, team_rating
from footystreams.domain.types import Duty, RoleId
from footystreams.domain.valuation import MarketValueInputs, compute_peak_age, market_value
from tests.factories.player import make_mental, make_player, make_technical
from tests.factories.roles import make_role_catalog


def test_compute_current_ability__uses_catalog_weights() -> None:
    catalog = make_role_catalog()
    player = make_player(technical=make_technical(finishing=90))
    ca = compute_current_ability(player, catalog)
    assert 1 <= ca <= 100


def test_build_profile__includes_signature_when_floors_met() -> None:
    catalog = make_role_catalog()
    player = make_player(
        technical=make_technical(finishing=90),
        mental=make_mental(composure=75),
    )
    profile = build_profile(player, catalog)
    assert "elite_finisher" in profile.signature_skills


def test_market_value__monotonic_in_ca() -> None:
    low = market_value(
        MarketValueInputs(
            ability_current=60,
            ability_potential=70,
            age=24,
            reputation=50,
            contract_years_left=3,
        )
    )
    high = market_value(
        MarketValueInputs(
            ability_current=80,
            ability_potential=70,
            age=24,
            reputation=50,
            contract_years_left=3,
        )
    )
    assert high >= low


def test_market_value__younger_high_pa_premium() -> None:
    older = market_value(
        MarketValueInputs(
            ability_current=70,
            ability_potential=90,
            age=28,
            reputation=50,
            contract_years_left=3,
        )
    )
    younger = market_value(
        MarketValueInputs(
            ability_current=70,
            ability_potential=90,
            age=22,
            reputation=50,
            contract_years_left=3,
        )
    )
    assert younger >= older


def test_market_value__longer_contract_worth_more() -> None:
    short = market_value(
        MarketValueInputs(
            ability_current=70,
            ability_potential=75,
            age=25,
            reputation=50,
            contract_years_left=2,
        )
    )
    long = market_value(
        MarketValueInputs(
            ability_current=70,
            ability_potential=75,
            age=25,
            reputation=50,
            contract_years_left=8,
        )
    )
    assert long > short


def test_compute_peak_age__fitness_delays_peak() -> None:
    early = compute_peak_age(natural_fitness=30, determination=40, injury_proneness=80)
    late = compute_peak_age(natural_fitness=90, determination=80, injury_proneness=20)
    assert late > early


def test_team_rating__requires_eleven() -> None:
    catalog = make_role_catalog()
    player = make_player()
    with pytest.raises(ValueError, match="11"):
        team_rating([(player, RoleId("poacher"), Duty.ATTACK)] * 10, catalog)


def test_team_rating__mean_of_assigned_roles() -> None:
    catalog = make_role_catalog()
    player = make_player()
    starters = [(player, RoleId("poacher"), Duty.ATTACK)] * 11
    rating = team_rating(starters, catalog)
    assert 0.0 <= rating <= 100.0
