"""verify_world on a real generated world, plus a canary per check proving it can fail."""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable

import pytest

from footystreams.domain.club import Rivalry
from footystreams.domain.media import MediaRole
from footystreams.domain.types import ClubId, EntityKind, EntityRef, FormationId, Id, NationId
from footystreams.domain.world import SquadEntry, World
from footystreams.verify import WorldChecks, WorldTargets, verify_world
from tests.factories.world import make_world, make_world_checks, make_world_targets
from tests.helpers.assertions import assert_no_violations


def _codes(
    world: World, targets: WorldTargets | None = None, checks: WorldChecks | None = None
) -> set[str]:
    found = verify_world(world, checks or make_world_checks(), targets or make_world_targets())
    return {violation.code for violation in found}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_verify_world__generated_worlds_are_coherent(seed: int) -> None:
    assert_no_violations(verify_world(make_world(seed), make_world_checks(), make_world_targets()))


# ---------------------------------------------------------------- W01 references
def test_w01__city_with_unknown_nation__flagged() -> None:
    world = make_world()
    cities = (
        world.cities[0].model_copy(update={"nation_id": NationId("nat_nowhere")}),
        *world.cities[1:],
    )
    assert "W01" in _codes(dataclasses.replace(world, cities=cities))


def test_w01__club_with_unknown_manager__flagged() -> None:
    world = make_world()
    club = world.clubs[0].model_copy(update={"manager_id": "mgr_unknown"})
    assert "W01" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w01__staff_id_not_employed_by_the_club__flagged() -> None:
    world = make_world()
    foreign_staff = next(s for s in world.staff if s.club_id != world.clubs[0].id)
    club = world.clubs[0].model_copy(
        update={"staff_ids": (*world.clubs[0].staff_ids, foreign_staff.id)}
    )
    assert "W01" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w01__academy_prospect_that_is_not_youth__flagged() -> None:
    world = make_world()
    senior = next(p for p in world.players if p.contract and not p.is_youth)
    academy = world.clubs[0].academy.model_copy(update={"prospect_ids": (senior.id,)})
    club = world.clubs[0].model_copy(update={"academy": academy})
    assert "W01" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w01__rivalry_with_self_or_unknown_club__flagged() -> None:
    world = make_world()
    rivalry = Rivalry(club_id=world.clubs[0].id, intensity=0.5)
    club = world.clubs[0].model_copy(update={"rivalries": (rivalry,)})
    assert "W01" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w01__unknown_club_nation__flagged() -> None:
    world = make_world()
    location = world.clubs[0].location.model_copy(update={"nation_id": NationId("nat_nowhere")})
    club = world.clubs[0].model_copy(update={"location": location})
    assert "W01" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w01__player_with_unknown_nationality_contract_club_or_career_club__flagged() -> None:
    world = make_world()
    player = next(p for p in world.players if p.contract and p.career_history)
    contract = player.contract.model_copy(update={"club_id": ClubId("clb_nowhere")})  # type: ignore[union-attr]
    stint = player.career_history[0].model_copy(update={"club_id": ClubId("clb_elsewhere")})
    broken = player.model_copy(
        update={
            "nationality": NationId("nat_nowhere"),
            "contract": contract,
            "career_history": (stint,),
        }
    )
    players = tuple(broken if p.id == player.id else p for p in world.players)
    assert "W01" in _codes(dataclasses.replace(world, players=players))


def test_w01__manager_contract_or_career_club_unknown__flagged() -> None:
    world = make_world()
    manager = next(m for m in world.managers if m.contract)
    contract = manager.contract.model_copy(update={"club_id": ClubId("clb_nowhere")})  # type: ignore[union-attr]
    stint = manager.career_history[0].model_copy(update={"club_id": ClubId("clb_elsewhere")})
    broken = manager.model_copy(update={"contract": contract, "career_history": (stint,)})
    managers = tuple(broken if m.id == manager.id else m for m in world.managers)
    assert "W01" in _codes(dataclasses.replace(world, managers=managers))


def test_w01__competition_and_ledger_with_unknown_club__flagged() -> None:
    world = make_world()
    competition = world.competitions[0].model_copy(update={"club_ids": (ClubId("clb_nowhere"),)})
    entry = world.ledger_opening[0].model_copy(update={"club_id": ClubId("clb_nowhere")})
    broken = dataclasses.replace(
        world, competitions=(competition,), ledger_opening=(entry, *world.ledger_opening[1:])
    )
    assert "W01" in _codes(broken)


def test_w01__relationship_endpoint_missing_or_self_link__flagged() -> None:
    world = make_world()
    ghost = EntityRef(kind=EntityKind.PLAYER, id=Id("plr_ghost"))
    row = world.relationships[0].model_copy(update={"b": ghost})
    self_link = world.relationships[1].model_copy(update={"b": world.relationships[1].a})
    broken = dataclasses.replace(world, relationships=(row, self_link, *world.relationships[2:]))
    assert "W01" in _codes(broken)


def test_w01__duplicate_person_id__flagged() -> None:
    world = make_world()
    clone = world.players[0].model_copy(update={"known_as": "Clone Only"})
    assert "W01" in _codes(dataclasses.replace(world, players=(*world.players, clone)))


# ------------------------------------------------------------ W07 / W08 registration
def test_w07__player_registered_twice__flagged() -> None:
    world = make_world()
    entry = world.squad_entries[0]
    twin = SquadEntry(
        club_id=world.squad_entries[-1].club_id,
        player_id=entry.player_id,
        squad_number=99,
        status=entry.status,
        squad_role=entry.squad_role,
    )
    assert "W07" in _codes(dataclasses.replace(world, squad_entries=(*world.squad_entries, twin)))


def test_w08__contractless_non_free_agent__flagged() -> None:
    world = make_world()
    target = next(p for p in world.players if p.contract)
    stripped = target.model_copy(update={"contract": None})
    players = tuple(stripped if p.id == target.id else p for p in world.players)
    assert "W08" in _codes(dataclasses.replace(world, players=players))


def test_w08__contract_club_squad_number_and_dates_must_agree() -> None:
    world = make_world()
    target = next(p for p in world.players if p.contract and not p.is_youth)
    contract = target.contract
    assert contract is not None
    other_club = next(c.id for c in world.clubs if c.id != contract.club_id)
    variants = [
        target.model_copy(update={"contract": contract.model_copy(update={"club_id": other_club})}),
        target.model_copy(update={"squad_number": 77}),
        target.model_copy(
            update={"contract": contract.model_copy(update={"end": dt.date(2000, 1, 1)})}
        ),
    ]
    for broken in variants:
        players = tuple(broken if p.id == target.id else p for p in world.players)
        assert "W08" in _codes(dataclasses.replace(world, players=players))


def test_w08__shirt_number_worn_twice_or_out_of_range__flagged() -> None:
    world = make_world()
    first, second = world.squad_entries[0], world.squad_entries[1]
    duplicate = second.model_copy(
        update={"club_id": first.club_id, "squad_number": first.squad_number}
    )
    assert "W08" in _codes(
        dataclasses.replace(world, squad_entries=(first, duplicate, *world.squad_entries[2:]))
    )
    unchecked = first.model_copy(update={"squad_number": 150})
    assert "W08" in _codes(
        dataclasses.replace(world, squad_entries=(unchecked, *world.squad_entries[1:]))
    )


# ------------------------------------------------------------------------ W02 squads
def _without_club_players(world: World, keep: Callable[[object], bool]) -> World:
    club = world.clubs[0].id
    players = tuple(
        p for p in world.players if not (p.contract and p.contract.club_id == club) or keep(p)
    )
    return dataclasses.replace(world, players=players)


def test_w02__small_squad_without_keepers_or_cover__flagged() -> None:
    world = _without_club_players(make_world(), lambda p: p.primary_position.value == "ST")  # type: ignore[attr-defined]
    found = verify_world(world, make_world_checks(), make_world_targets())
    messages = " ".join(v.message for v in found if v.code == "W02")
    assert "goalkeepers" in messages
    assert "bench" in messages
    assert "senior squad" in messages


def test_w02__formation_missing_from_catalogue__flagged() -> None:
    world = make_world()
    tactics = world.clubs[0].default_tactics.model_copy(update={"formation": FormationId("999")})
    club = world.clubs[0].model_copy(update={"default_tactics": tactics})
    assert "W02" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


# ------------------------------------------------------------------------ W03 money
def test_w03__balance_that_differs_from_the_ledger__flagged() -> None:
    world = make_world()
    finances = world.clubs[0].finances.model_copy(
        update={"balance": world.clubs[0].finances.balance + 1}
    )
    club = world.clubs[0].model_copy(update={"finances": finances})
    assert "W03" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w03__wage_bill_far_from_budget__flagged() -> None:
    world = make_world()
    finances = world.clubs[0].finances.model_copy(update={"wage_budget_weekly": 1})
    club = world.clubs[0].model_copy(update={"finances": finances})
    assert "W03" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_w03__too_many_overspending_clubs__flagged() -> None:
    world = make_world()
    clubs = tuple(
        c.model_copy(
            update={
                "finances": c.finances.model_copy(
                    update={"wage_budget_weekly": round(c.finances.wage_budget_weekly * 0.8)}
                )
            }
        )
        for c in world.clubs
    )
    assert "W03" in _codes(dataclasses.replace(world, clubs=clubs))


# --------------------------------------------------------------- W09 / W10 ability
def test_w09_w10__potential_below_current_and_stale_cached_ability__flagged() -> None:
    world = make_world()
    target = world.players[0]
    broken = target.model_copy(update={"ability_potential": 1, "ability_current": 99})
    players = (broken, *world.players[1:])
    assert {"W09", "W10"} <= _codes(dataclasses.replace(world, players=players))


# ----------------------------------------------------------------------- C01-C08
def test_c01_c02__duplicate_known_as_repeated_surname_and_denied_name__flagged() -> None:
    world = make_world()
    players = list(world.players)
    players[1] = players[1].model_copy(update={"known_as": players[0].known_as})
    for index in (2, 3, 4):
        players[index] = players[index].model_copy(update={"last_name": "Sharedname"})
    players[5] = players[5].model_copy(update={"last_name": "Messi"})
    found = _codes(dataclasses.replace(world, players=tuple(players)))
    assert {"C01", "C02"} <= found


def test_c01__kin_may_share_a_surname() -> None:
    world = make_world()
    kin_ids = {
        end.id for row in world.relationships if row.kind == "family" for end in (row.a, row.b)
    }
    assert kin_ids, "default seed should contain a kin pair"
    players = tuple(
        p.model_copy(update={"last_name": "Sharedname"}) if p.id in kin_ids else p
        for p in world.players
    )
    assert "C01" not in _codes(dataclasses.replace(world, players=players))


def test_c03__one_nation_dominating_a_squad__flagged() -> None:
    world = make_world()
    home = world.nations[0].id
    players = tuple(p.model_copy(update={"nationality": home}) for p in world.players)
    assert "C03" in _codes(dataclasses.replace(world, players=players))


def test_c04__referees_without_characters__flagged() -> None:
    world = make_world()
    referees = tuple(
        r.model_copy(update={"strictness": 0.5, "card_tendency": 0.5, "home_bias": 0.45})
        for r in world.referees
    )
    assert "C04" in _codes(dataclasses.replace(world, referees=referees))


def test_c05__crew_with_missing_role_clashing_voice_and_clone_personality__flagged() -> None:
    world = make_world()
    crew = list(world.media)
    crew = [m for m in crew if m.role is not MediaRole.PUNDIT]
    clash = crew[1].voice.model_copy(update={"bindings": crew[0].voice.bindings})
    crew[1] = crew[1].model_copy(update={"voice": clash, "personality": crew[0].personality})
    assert "C05" in _codes(dataclasses.replace(world, media=tuple(crew)))


def test_c06__manager_formation_outside_the_catalogue_or_not_his_best__flagged() -> None:
    world = make_world()
    odd = world.managers[0].model_copy(update={"preferred_formation": FormationId("999")})
    proficiency = dict(world.managers[1].formation_proficiency)
    proficiency[world.managers[1].preferred_formation] = 1
    flat = world.managers[1].model_copy(update={"formation_proficiency": proficiency})
    broken = dataclasses.replace(world, managers=(odd, flat, *world.managers[2:]))
    assert "C06" in _codes(broken)


def test_c07__academy_listing_the_wrong_players__flagged() -> None:
    world = make_world()
    academy = world.clubs[0].academy.model_copy(update={"prospect_ids": ()})
    club = world.clubs[0].model_copy(update={"academy": academy})
    assert "C07" in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))


def test_c08__league_shape_violations_and_single_club_leagues() -> None:
    world = make_world()
    wide = dataclasses.replace(make_world_targets(), min_team_gap=99.0, max_team_gap=100.0)
    assert "C08" in _codes(world, wide)
    tight = dataclasses.replace(make_world_targets(), min_adjacent_gap=50.0)
    assert "C08" in _codes(world, tight)
    solo = dataclasses.replace(world, clubs=world.clubs[:1])
    assert "C08" not in _codes(solo)


def test_w01__club_without_a_manager_is_allowed() -> None:
    world = make_world()
    club = world.clubs[0].model_copy(update={"manager_id": None})
    assert "W01" not in _codes(dataclasses.replace(world, clubs=(club, *world.clubs[1:])))
