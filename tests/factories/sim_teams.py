"""Position-aware demo teams for the simulation: setups with a sensible strength profile.

`make_demo_setup(home_strength=70, away_strength=55)` gives two full sheets whose players are
specialists for their formation slots (keeper, defenders, midfielders, forwards), scaled by a single
`strength` number (about 40-90). Used by the sim tests, the statistical sweeps and the `sim --demo`
CLI. Nothing here draws random numbers: variation comes from the slot index.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from footystreams.domain.club import ClubColours, Fanbase, KitSpec
from footystreams.domain.match import (
    ClubSnapshot,
    CornerTakers,
    LineupSlot,
    ManagerSnapshot,
    MatchSetup,
    PolicyRef,
    TeamSheet,
)
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.tactics import Mentality, SlotAssignment, TeamTactics
from footystreams.domain.tactics.modules.v1 import BuildUp, ModuleKey, Pressing
from footystreams.domain.types import (
    ClubId,
    Duty,
    FixtureId,
    FormationId,
    ManagerId,
    MatchId,
    PlayerId,
    Position,
    RefereeId,
    RoleId,
)
from footystreams.domain.weather import Weather, WeatherCondition
from footystreams.sim.formations import BUILTIN_FORMATIONS
from tests.factories.match import make_player_snapshot, make_team_sheet
from tests.factories.player import (
    make_goalkeeping,
    make_hidden,
    make_mental,
    make_physical,
    make_technical,
)

DEMO_REFEREE_ID = RefereeId("ref_demo0001")  # the official every demo setup names
_FIRST_NAMES = (
    "Brae", "Kell", "Davo", "Mirek", "Tovan", "Sasha", "Ruben", "Jarek", "Ollie", "Pavel",
    "Nando", "Lucan", "Emre", "Tomas", "Arlo", "Viktor", "Hale", "Oren", "Dario", "Soren",
    "Kasim", "Bram", "Idris", "Yann", "Lior", "Matej", "Rafe", "Zane",
)  # fmt: skip
_BENCH_POSITIONS = (Position.GK, Position.CM, Position.ST)
_ROLE_BY_POSITION = {
    Position.GK: "keeper_classic",
    Position.CB: "stopper_cb",
    Position.RB: "fullback_overlap",
    Position.LB: "fullback_overlap",
    Position.RWB: "wingback_attacking",
    Position.LWB: "wingback_attacking",
    Position.DM: "anchor",
    Position.CM: "shuttler",
    Position.AM: "deep_creator",
    Position.RM: "winger_classic",
    Position.LM: "winger_classic",
    Position.RW: "winger_classic",
    Position.LW: "winger_classic",
    Position.SS: "shadow_striker",
    Position.ST: "poacher",
}
_DEFENDERS = {Position.CB, Position.RB, Position.LB, Position.RWB, Position.LWB}
_MIDFIELDERS = {Position.DM, Position.CM, Position.AM, Position.RM, Position.LM}
_COMPETENT = 90
_NEIGHBOUR = 60
_STRENGTH_STEP = 2
_SPECIALIST_EDGE = 8
_WEAK_SKILL_GAP = 22


def _bounded(value: float) -> int:
    return max(1, min(100, round(value)))


def _profile(position: Position, strength: int, index: int) -> Mapping[str, Mapping[str, int]]:
    """Return attribute overrides per group for a specialist at `position`."""
    wobble = (index % 3 - 1) * _STRENGTH_STEP
    base = strength + wobble
    high, low = base + _SPECIALIST_EDGE, base - _WEAK_SKILL_GAP
    if position is Position.GK:
        keeper = {name: _bounded(high) for name in ("handling", "shot_stopping", "one_on_ones")} | {
            "aerial_command": _bounded(base),
            "sweeping": _bounded(base),
            "distribution": _bounded(base),
            "communication": _bounded(base),
        }
        return {
            "technical": {name: _bounded(low) for name in ("finishing", "dribbling", "long_shots")},
            "goalkeeping": keeper,
        }
    if position in _DEFENDERS:
        names = ("tackling", "marking", "heading")
        return {
            "technical": {name: _bounded(high) for name in names}
            | {"finishing": _bounded(low), "dribbling": _bounded(base - 10)},
            "mental": {"positioning": _bounded(high), "anticipation": _bounded(high)},
        }
    if position in _MIDFIELDERS:
        names = ("short_passing", "long_passing", "first_touch")
        return {
            "technical": {name: _bounded(high) for name in names}
            | {"finishing": _bounded(base - 8)},
            "mental": {"vision": _bounded(high), "decisions": _bounded(high)},
        }
    return {
        "technical": {"finishing": _bounded(high), "dribbling": _bounded(high),
                      "tackling": _bounded(low), "marking": _bounded(low)},
        "mental": {"off_ball_movement": _bounded(high), "composure": _bounded(base + 4)},
        "physical": {"pace": _bounded(high)},
    }  # fmt: skip


def _competence(position: Position) -> dict[Position, int]:
    competence = dict.fromkeys(Position, 10)
    competence[position] = _COMPETENT
    for neighbour in _NEIGHBOURS.get(position, ()):
        competence[neighbour] = _NEIGHBOUR
    return competence


_NEIGHBOURS: Mapping[Position, tuple[Position, ...]] = {
    Position.RB: (Position.RWB, Position.CB),
    Position.LB: (Position.LWB, Position.CB),
    Position.CB: (Position.RB, Position.LB, Position.DM),
    Position.DM: (Position.CM, Position.CB),
    Position.CM: (Position.DM, Position.AM),
    Position.AM: (Position.CM, Position.SS),
    Position.RM: (Position.RW, Position.CM),
    Position.LM: (Position.LW, Position.CM),
    Position.RW: (Position.RM, Position.ST),
    Position.LW: (Position.LM, Position.ST),
    Position.SS: (Position.ST, Position.AM),
    Position.ST: (Position.SS, Position.RW, Position.LW),
}


def _snapshot(
    player_id: str, name: str, number: int, position: Position, strength: int
) -> PlayerSnapshot:
    groups = _profile(position, strength, number)
    flat = {
        "technical": make_technical(
            **{"finishing": 50, **_flat(strength), **groups.get("technical", {})}
        ),
        "mental": make_mental(**{**_flat_mental(strength), **groups.get("mental", {})}),
        "physical": make_physical(**{**_flat_physical(strength), **groups.get("physical", {})}),
        "goalkeeping": make_goalkeeping(**groups.get("goalkeeping", {})),
        "hidden": make_hidden(),
    }
    return make_player_snapshot(
        id=PlayerId(player_id),
        known_as=name,
        squad_number=number,
        position_competence=_competence(position),
        **flat,
    )


def _flat(strength: int) -> dict[str, int]:
    return dict.fromkeys(
        (
            "long_shots", "heading", "first_touch", "dribbling", "short_passing", "long_passing",
            "crossing", "tackling", "marking", "set_piece_delivery", "penalty_taking",
            "ball_shielding",
        ),
        _bounded(strength - 4),
    )  # fmt: skip


def _flat_mental(strength: int) -> dict[str, int]:
    names = (
        "vision", "decisions", "composure", "anticipation", "positioning", "off_ball_movement",
        "work_rate", "aggression", "bravery", "concentration", "determination", "teamwork", "flair",
        "leadership",
    )  # fmt: skip
    return dict.fromkeys(names, _bounded(strength))


def _flat_physical(strength: int) -> dict[str, int]:
    names = ("pace", "acceleration", "stamina", "strength", "agility", "balance", "jumping_reach")
    return {**dict.fromkeys(names, _bounded(strength)), "natural_fitness": 60}


def make_demo_sheet(  # noqa: PLR0913 - a demo team is described by these independent knobs
    side: str,
    *,
    strength: int = 60,
    formation: str = "433",
    mentality: Mentality = Mentality.BALANCED,
    club: tuple[str, str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> TeamSheet:
    """Build a position-aware sheet; `club` is `(club_id, name, short_code)`."""
    club_id, club_name, code = club or (f"clb_{side}01", side.title(), side[:3].upper())
    rows = BUILTIN_FORMATIONS[formation]
    positions = [Position(code_) for code_, _, _ in rows]
    offset = 0 if side == "home" else len(_FIRST_NAMES) // 2
    ids = [PlayerId(f"plr_{side}{index:04d}") for index in range(len(positions) + 3)]
    squad: dict[PlayerId, PlayerSnapshot] = {}
    for index, player_id in enumerate([*ids[: len(positions)]]):
        name = _FIRST_NAMES[(index + offset) % len(_FIRST_NAMES)]
        squad[player_id] = _snapshot(player_id, name, index + 1, positions[index], strength)
    bench_ids = ids[len(positions) :]
    for index, (player_id, position) in enumerate(zip(bench_ids, _BENCH_POSITIONS, strict=True)):
        number = len(positions) + index + 1
        squad[player_id] = _snapshot(
            player_id, f"{club_name[:6]}{number}", number, position, strength - 8
        )
    lineup = tuple(
        LineupSlot(
            slot=index,
            player_id=ids[index],
            role=RoleId(_ROLE_BY_POSITION[positions[index]]),
            duty=Duty.SUPPORT,
        )
        for index in range(len(positions))
    )
    sheet = TeamSheet(
        club=ClubSnapshot(
            id=ClubId(club_id),
            name=club_name,
            short_code=code,
            colours=_colours(),
            reputation=60,
        ),
        manager=_manager(side),
        lineup=lineup,
        bench=tuple(bench_ids),
        squad=squad,
        tactics=_tactics(formation, lineup, mentality),
        policy=PolicyRef(policy_id="rules", policy_version="v1"),
        captain_id=ids[5],
        penalty_takers=(ids[len(positions) - 1], ids[len(positions) - 2]),
        free_kick_takers=(ids[5], ids[len(positions) - 1]),
        corner_takers=CornerTakers(left=ids[7], right=ids[8]),
        fanbase=Fanbase(size=20_000, passion=0.6, toxicity=0.3, fickleness=0.4, away_following=0.3),
    )
    return sheet.model_copy(update=dict(overrides)) if overrides else sheet


def _colours() -> ClubColours:
    return ClubColours(
        primary="#111111",
        secondary="#eeeeee",
        accent="#ff0000",
        home_kit=KitSpec(),
        away_kit=KitSpec(),
    )


def _manager(side: str) -> ManagerSnapshot:
    template = make_team_sheet(side=side).manager
    return template.model_copy(update={"id": ManagerId(f"mgr_{side}0001")})


def _tactics(formation: str, lineup: tuple[LineupSlot, ...], mentality: Mentality) -> TeamTactics:
    return TeamTactics(
        formation=FormationId(formation),
        slots=tuple(
            SlotAssignment(slot=item.slot, role=item.role, duty=item.duty) for item in lineup
        ),
        mentality=mentality,
        modules={ModuleKey.BUILD_UP: BuildUp(), ModuleKey.PRESSING: Pressing(intensity=0.6)},
    )


def make_demo_setup(  # noqa: PLR0913 - a demo match is described by these independent knobs
    *,
    home_strength: int = 60,
    away_strength: int = 60,
    home_formation: str = "433",
    away_formation: str = "433",
    match_id: str = "mch_demo0001",
    weather: Weather | None = None,
) -> MatchSetup:
    """Build a full setup between two position-aware teams (a derby-free, neutral-weather match)."""
    return MatchSetup(
        match_id=MatchId(match_id),
        fixture_id=FixtureId("fix_demo0001"),
        home=make_demo_sheet(
            "home",
            strength=home_strength,
            formation=home_formation,
            club=("clb_kes001", "Kestrel Town", "KES"),
        ),
        away=make_demo_sheet(
            "away",
            strength=away_strength,
            formation=away_formation,
            club=("clb_har001", "Harbour United", "HAR"),
        ),
        weather=weather or _fair_weather(),
        referee_id=DEMO_REFEREE_ID,
        attendance=18_000,
        is_derby=False,
        importance=0.5,
    )


def _fair_weather() -> Weather:
    return Weather(
        condition=WeatherCondition.CLEAR,
        temperature_c=16.0,
        humidity=0.5,
        wind_speed_mps=2.0,
        wind_direction_deg=90,
        rain_mm_per_h=0.0,
        pitch_wetness=0.1,
        visibility=1.0,
    )
