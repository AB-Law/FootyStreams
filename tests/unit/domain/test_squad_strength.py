from __future__ import annotations

import pytest

from footystreams.domain.ratings import ability_from_attributes, compute_current_ability
from footystreams.domain.squad_strength import best_lineup, squad_strength
from footystreams.domain.types import Position
from tests.factories.player import make_goalkeeping, make_player, make_technical
from tests.factories.roles import make_role_catalog
from tests.factories.tactics import make_team_tactics

CATALOG = make_role_catalog()


def test_ability_from_attributes__matches_compute_current_ability() -> None:
    player = make_player(technical=make_technical(finishing=88))
    flat = {
        **player.technical.model_dump(),
        **player.mental.model_dump(),
        **player.physical.model_dump(),
        **player.goalkeeping.model_dump(),
        **player.hidden.model_dump(),
    }
    expected = compute_current_ability(player, CATALOG)
    assert ability_from_attributes(flat, player.position_competence, CATALOG) == expected


def test_ability_from_attributes__no_competent_position__clamps_to_minimum() -> None:
    assert ability_from_attributes({"finishing": 99}, {}, CATALOG) == 1


def test_best_lineup__fewer_than_eleven__raises() -> None:
    with pytest.raises(ValueError, match="at least 11"):
        best_lineup([make_player()], make_team_tactics(), CATALOG)


def test_best_lineup__keeper_slot_goes_first_and_takes_the_keeper() -> None:
    keeper = make_player(
        id="plr_gk000001",
        known_as="Keeper",
        goalkeeping=make_goalkeeping(shot_stopping=90, handling=90, sweeping=80),
        position_competence={Position.GK: 98},
    )
    outfield = [make_player(id=f"plr_of{i:04d}", known_as=f"Out{i}") for i in range(10)]
    tactics = make_team_tactics()
    slots = list(tactics.slots)
    slots[0] = slots[0].model_copy(update={"role": "sweeper_keeper"})
    tactics = tactics.model_copy(update={"slots": tuple(slots)})
    lineup = best_lineup([*outfield, keeper], tactics, CATALOG)
    assert lineup[0][0].id == keeper.id


def test_squad_strength__better_players__higher_rating() -> None:
    weak = [make_player(id=f"plr_wk{i:04d}", known_as=f"W{i}") for i in range(11)]
    strong = [
        make_player(id=f"plr_sg{i:04d}", known_as=f"S{i}", technical=make_technical(finishing=90))
        for i in range(11)
    ]
    tactics = make_team_tactics()
    assert squad_strength(strong, tactics, CATALOG) > squad_strength(weak, tactics, CATALOG)
