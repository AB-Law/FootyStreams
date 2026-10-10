"""Wider-world club catalog: fixed ids and speakable names for career history."""

from __future__ import annotations

from footystreams.domain.world import WIDER_WORLD_CLUB_COUNT, WIDER_WORLD_PREFIX
from tests.factories.world import make_world


def test_wider_clubs__forty_named_stubs_with_stable_ids() -> None:
    world = make_world(1)
    assert len(world.wider_clubs) == WIDER_WORLD_CLUB_COUNT
    assert [club.id for club in world.wider_clubs] == [
        f"{WIDER_WORLD_PREFIX}{index:03d}" for index in range(1, WIDER_WORLD_CLUB_COUNT + 1)
    ]
    names = {club.name for club in world.wider_clubs}
    assert len(names) == WIDER_WORLD_CLUB_COUNT
    league_names = {club.name for club in world.clubs}
    assert names.isdisjoint(league_names)


def test_wider_clubs__career_stints_resolve_to_catalog() -> None:
    world = make_world(1)
    by_id = {club.id: club for club in world.wider_clubs}
    referenced = {
        stint.club_id
        for player in world.players
        for stint in player.career_history
        if str(stint.club_id).startswith(WIDER_WORLD_PREFIX)
    }
    assert referenced
    assert referenced <= set(by_id)
