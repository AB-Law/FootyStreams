"""Building the initial match state from a setup: teams, players on their slots, fatigue fields.

Everything here runs once per match (and, for a substitute, once when he comes on). Draws come
from the `dayform` stream only: one Irwin-Hall value per player.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.match import LineupSlot, MatchSetup, TeamSheet
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import FormationId
from footystreams.sim.config import SimConfig
from footystreams.sim.effective import Skills, build_skills, day_form_multiplier, multipliers
from footystreams.sim.errors import InvalidSetupError
from footystreams.sim.fatigue import away_travel, initial_exhaustion, player_drain
from footystreams.sim.geometry import frame_coordinate
from footystreams.sim.homeadv import NO_CROWD, Crowd, apply_crowd, crowd_of
from footystreams.sim.rng import SimRng
from footystreams.sim.side import Side
from footystreams.sim.state import MatchState, PlayerState, TeamState, line_of
from footystreams.sim.tables import Formation, StaticTables
from footystreams.sim.tactics_view import build_view
from footystreams.sim.weather import Conditions, apply_conditions, conditions_for


@dataclass(frozen=True, slots=True)
class BuildContext:
    """What building a player needs besides his snapshot: day-form stream, conditions, config."""

    day_rng: SimRng
    conditions: Conditions
    config: SimConfig
    crowd: Crowd = NO_CROWD


def make_context(setup: MatchSetup, day_rng: SimRng, config: SimConfig) -> BuildContext:
    """Gather what players are built with: the day-form stream, conditions and the crowd."""
    conditions = conditions_for(setup.weather, setup.home.stadium, config.weather)
    return BuildContext(day_rng, conditions, config, crowd_of(setup, config.home_advantage))


def build_state(setup: MatchSetup, tables: StaticTables, context: BuildContext) -> MatchState:
    """Build the initial state: players on their slots, home to kick off in period 1."""
    home = _build_team("home", setup.home, tables, context)
    away = _build_team("away", setup.away, tables, context)
    return MatchState(
        home=home,
        away=away,
        carrier=home.players[0],
        is_derby=setup.is_derby,
        attendance=setup.attendance,
        conditions=context.conditions,
    )


def _build_team(
    side: Side, sheet: TeamSheet, tables: StaticTables, context: BuildContext
) -> TeamState:
    formation_id = sheet.tactics.formation
    formation = tables.formations.get(FormationId(formation_id))
    if formation is None:
        msg = f"unknown formation {formation_id!r} on {sheet.club.id}"
        raise InvalidSetupError(msg)
    attack_dir = 1 if side == "home" else -1
    ordered = sorted(sheet.lineup, key=lambda lineup_slot: lineup_slot.slot)
    players = [build_player(side, sheet, formation, item, context) for item in ordered]
    team = TeamState(side, sheet, formation, build_view(sheet), attack_dir, players)
    team.bench = list(sheet.bench)
    return team


def build_player(
    side: Side,
    sheet: TeamSheet,
    formation: Formation,
    lineup_slot: LineupSlot,
    context: BuildContext,
) -> PlayerState:
    """Build one player standing on a formation slot (starters and substitutes alike)."""
    snapshot: PlayerSnapshot = sheet.squad[lineup_slot.player_id]
    formation_slot = formation.slots[lineup_slot.slot]
    day = day_form_multiplier(snapshot.hidden.consistency, context.day_rng)
    mult = multipliers(snapshot, formation_slot.position, lineup_slot.role, day)
    attack_dir = 1 if side == "home" else -1
    player = PlayerState(
        player_id=lineup_slot.player_id,
        side=side,
        slot=lineup_slot.slot,
        position=formation_slot.position,
        line=line_of(formation_slot.position),
        role=lineup_slot.role,
        skills=_with_crowd(
            apply_conditions(build_skills(snapshot, mult), context.conditions), side, context
        ),
        base_x=formation_slot.x,
        base_y=formation_slot.y,
        x=frame_coordinate(formation_slot.x, attack_dir),
        y=frame_coordinate(formation_slot.y, attack_dir),
        shirt=snapshot.squad_number,
    )
    return _with_fatigue(player, snapshot, sheet, context)


def _with_crowd(skills: Skills, side: Side, context: BuildContext) -> Skills:
    """Apply the home-advantage crowd to a player's skills (identity when it is off)."""
    config = context.config
    return apply_crowd(
        skills, side, context.crowd, config.home_advantage, config.home_advantage_scale
    )


def _with_fatigue(
    player: PlayerState, snapshot: PlayerSnapshot, sheet: TeamSheet, context: BuildContext
) -> PlayerState:
    """Record the pre-fatigue skills and, when fatigue is on, his starting exhaustion and drain."""
    cfg = context.config.fatigue
    player.base_skills = player.skills
    if not cfg.enabled:
        return player
    player.exhaustion = initial_exhaustion(snapshot, cfg)
    travel = away_travel(sheet if player.side == "away" else None, cfg)
    player.drain = player_drain(player, context.conditions, travel, cfg)
    return player
