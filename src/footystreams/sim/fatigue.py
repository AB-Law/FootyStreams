"""Fatigue: in-match exhaustion that only rises during play and weakens skills in bounded steps.

`E` starts from carried-in tiredness and lack of conditioning, then grows with time at a rate set
by stamina, natural fitness, work rate, role, pressing, tempo, heat, a wet pitch, travel and
playing a man down. It never falls during play; the half-time recovery is the one declared
exception (docs/design/02 section 9). Skills are rebuilt from `base_skills` only when `E` crosses
a refresh step, so the cost is a few rebuilds per player per match.
"""

from __future__ import annotations

from footystreams.domain.match import TeamSheet
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import PlayerId
from footystreams.sim.config_world import FatigueConfig
from footystreams.sim.effective import Multipliers, scale_skills
from footystreams.sim.mathx import clamp
from footystreams.sim.state import Line, MatchState, PlayerState, TeamState
from footystreams.sim.weather import Conditions

_PERCENT = 100.0
FINAL_PRECISION = 4
_CENTRE = 0.5


def initial_exhaustion(snapshot: PlayerSnapshot, cfg: FatigueConfig) -> float:
    """Return starting exhaustion: carried-in fatigue plus lack of conditioning, in [0, 1]."""
    carried = cfg.carried_fatigue_weight * snapshot.fatigue
    unfit = cfg.carried_fitness_weight * (1.0 - snapshot.fitness)
    return clamp(carried + unfit, 0.0, 1.0)


def role_load(line: Line, cfg: FatigueConfig) -> float:
    """Return how demanding the player's row of the team is."""
    return (cfg.keeper_load, cfg.defence_load, cfg.midfield_load, cfg.attack_load)[line]


def player_drain(
    player: PlayerState, conditions: Conditions, travel: float, cfg: FatigueConfig
) -> float:
    """Return the player's static drain: his condition, role, the weather and the journey.

    `(1.1 - 0.5 stamina) x (1.05 - 0.25 fitness) x role x (1 + 0.5 heat) x (1 + 0.25 wet)
    x (0.75 + 0.5 work rate) x (1 + travel)`, each rating on a 0-1 scale.
    """
    skills = player.skills
    condition = (1.1 - cfg.stamina_weight * skills.stamina / _PERCENT) * (
        1.05 - cfg.fitness_weight * skills.natural_fitness / _PERCENT
    )
    effort = (
        1.0 - cfg.work_rate_weight * _CENTRE + cfg.work_rate_weight * skills.work_rate / _PERCENT
    )
    weather = (1.0 + cfg.heat_weight * conditions.heat) * (1.0 + cfg.wet_weight * conditions.wet)
    return (
        cfg.base_rate * condition * role_load(player.line, cfg) * effort * weather * (1.0 + travel)
    )


def away_travel(home_sheet: TeamSheet | None, cfg: FatigueConfig) -> float:
    """Return the extra drain an away side feels: travel weight and altitude of the home ground.

    `home_sheet` is the *home* sheet for an away player and None for a home player (no travel).
    """
    stadium = home_sheet.stadium if home_sheet is not None else None
    if stadium is None:
        return 0.0 if home_sheet is None else cfg.travel_weight * _CENTRE
    altitude = clamp(stadium.altitude_m / cfg.altitude_scale_m, 0.0, cfg.altitude_cap)
    return cfg.travel_weight * stadium.home_advantage.travel_weight + altitude


def team_factor(team: TeamState, cfg: FatigueConfig) -> float:
    """Return the team-wide multiplier: pressing, tempo and playing a man down."""
    view = team.view
    press = 1.0 + cfg.press_swing * (view.press_intensity - _CENTRE)
    tempo = 1.0 + cfg.tempo_swing * (view.tempo - _CENTRE)
    short = cfg.ten_men_load if len(team.players) < len(team.formation.slots) else 0.0
    return press * tempo * (1.0 + short)


def energy_multipliers(exhaustion: float, cfg: FatigueConfig) -> Multipliers:
    """Return the skill multipliers for an exhaustion level (physical first, mental last)."""
    physical = 1.0 - cfg.physical_k * exhaustion * exhaustion
    over_mental = max(0.0, exhaustion - cfg.mental_onset)
    over_technical = max(0.0, exhaustion - cfg.technical_onset)
    return Multipliers(
        technical=1.0 - cfg.technical_k * over_technical * over_technical,
        mental=1.0 - cfg.mental_k * over_mental * over_mental,
        physical=physical,
    )


def _refresh(player: PlayerState, cfg: FatigueConfig) -> None:
    """Rebuild a player's skills when his exhaustion has crossed into a new step."""
    step = int(player.exhaustion / cfg.refresh_step)
    if step != player.energy_step and player.base_skills is not None:
        player.energy_step = step
        player.skills = scale_skills(player.base_skills, energy_multipliers(player.exhaustion, cfg))


def advance_exhaustion(state: MatchState, dt: float, cfg: FatigueConfig) -> None:
    """Add `dt` seconds of exhaustion to every player on the pitch (never subtracts)."""
    for team in (state.home, state.away):
        scale = dt / cfg.match_s * team_factor(team, cfg)
        for player in team.players:
            gained = player.drain * scale
            player.exhaustion = min(cfg.max_exhaustion, player.exhaustion + gained)
            _refresh(player, cfg)


def halftime_recovery(state: MatchState, cfg: FatigueConfig) -> None:
    """Apply the declared half-time recovery: the only moment exhaustion falls."""
    for team in (state.home, state.away):
        for player in team.players:
            player.exhaustion = max(0.0, player.exhaustion - cfg.halftime_recovery)
            _refresh(player, cfg)


def final_exhaustion(state: MatchState) -> dict[PlayerId, float]:
    """Return every player's exhaustion (capped at 1) as he left the pitch or at the whistle."""
    found: dict[PlayerId, float] = {}
    for team in (state.home, state.away):
        for player in (*team.substituted_off, *team.sent_off, *team.players):
            found[player.player_id] = round(min(1.0, player.exhaustion), FINAL_PRECISION)
    return found
