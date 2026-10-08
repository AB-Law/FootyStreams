"""In-match injuries: when a player is hurt, how it looks, and who leaves the pitch.

Contacts (a called foul, a clean tackle) and a low background rate of strains roll against a
per-player hazard from proneness, tiredness, bravery, balance and the pitch. A hurt player who
cannot continue is replaced from the bench (a forced change, outside the window limit) or, with
no change available, the side plays short. Draws come from the `injury` stream only, so
re-tuning injuries never reshuffles who scores (docs/design/02 sections 1 and 9).
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.injury import InjurySeverity
from footystreams.events.discipline import InjuryEvent
from footystreams.events.summary_rows import InjuryReport
from footystreams.sim.actions.cards import remove_from_pitch
from footystreams.sim.actions.nearest import closest_of
from footystreams.sim.config_world import InjuryConfig
from footystreams.sim.emit import Meta
from footystreams.sim.injury_types import InjuryCause, InjuryType, base_days_of, types_for
from footystreams.sim.play import Play, actor, label, take_possession
from footystreams.sim.state import REGULATION_PERIOD_S, InjuryCase, MatchState, PlayerState
from footystreams.sim.subs import Window, can_change, make_substitution, replacement_for
from footystreams.sim.weather import Conditions

PERCENT = 100.0
_NEUTRAL_BRAVERY = 50.0
_HALF = 0.5
_MATCH_S = 2 * REGULATION_PERIOD_S
_APPARENT = {
    InjurySeverity.KNOCK: "looks_minor",
    InjurySeverity.MINOR: "needs_treatment",
    InjurySeverity.MODERATE: "looks_serious",
    InjurySeverity.SEVERE: "looks_serious",
}


@dataclass(frozen=True, slots=True)
class Incident:
    """What hurt whom: the victim, the cause, the other player involved and the event behind it."""

    victim: PlayerState
    cause: InjuryCause
    other: PlayerState | None
    caused_by: str | None


def hazard_multiplier(player: PlayerState, conditions: Conditions, cfg: InjuryConfig) -> float:
    """Return how much more (or less) likely than average this player is to be hurt.

    Each factor is 1.0 for an average, rested player on a good pitch: injury proneness, tiredness
    (exhaustion squared), bravery, balance (steady players ride contact out) and the pitch.
    """
    skills = player.skills
    proneness = cfg.proneness_floor + skills.injury_proneness / PERCENT
    tired = 1.0 + cfg.exhaustion_weight * player.exhaustion * player.exhaustion
    bravery = (1.0 + cfg.bravery_weight * skills.bravery / PERCENT) / (
        1.0 + cfg.bravery_weight * _NEUTRAL_BRAVERY / PERCENT
    )
    balance = (1.0 + _NEUTRAL_BRAVERY / cfg.balance_scale) / (
        1.0 + skills.balance / cfg.balance_scale
    )
    return proneness * tired * bravery * balance * conditions.injury_mult


def _stoppage_s(play: Play, severity: InjurySeverity) -> float:
    cfg = play.cfg.injury
    if severity is InjurySeverity.KNOCK:
        base = cfg.knock_stoppage_s
    elif severity is InjurySeverity.MINOR:
        base = cfg.minor_stoppage_s
    else:
        base = cfg.serious_stoppage_s
    return base + cfg.stoppage_spread_s * (play.injury.u() - _HALF) * 2.0


def _pick_type(play: Play, cause: InjuryCause) -> InjuryType:
    table = types_for(cause)
    return table[play.injury.choice_weighted([entry.weight for entry in table])]


def _wants_off(play: Play, severity: InjurySeverity) -> bool:
    """True when the injury is bad enough that the player cannot carry on."""
    if severity is InjurySeverity.KNOCK:
        return False
    if severity is InjurySeverity.MINOR:
        return play.injury.u() < play.cfg.injury.minor_off_share
    return True


def _leave_short(play: Play, victim: PlayerState) -> None:
    """Take the victim off with nobody to replace him; the ball goes to his nearest mate."""
    state = play.state
    team = state.team(victim.side)
    remove_from_pitch(team, victim, team.substituted_off)
    if state.assist_from is victim:
        state.assist_from = None
    if state.carrier is victim:
        take_possession(state, closest_of(team.players, (victim.x, victim.y)), victim.x, victim.y)


def _emit_injury(
    play: Play, incident: Incident, kind: InjuryType, stoppage: float, *, leaves: bool
) -> None:
    victim, other = incident.victim, incident.other
    team = play.state.team(victim.side)
    participants = [actor(victim, "injured")]
    if other is not None:
        participants.append(actor(other, "other"))
    meta = Meta(
        team=victim.side,
        participants=tuple(participants),
        pos=(victim.x, victim.y),
        caused_by=incident.caused_by,
        headline=f"{label(team, victim.player_id)} goes down injured",
    )
    play.emit.emit(
        play.state,
        InjuryEvent,
        meta,
        player_id=victim.player_id,
        cause=incident.cause,
        body_part=kind.body_part,
        apparent_severity=_APPARENT[kind.severity],
        can_continue=not leaves,
        stoppage_s=round(stoppage),
        caused_by_player_id=None if other is None else other.player_id,
    )


def injure(play: Play, incident: Incident) -> float:
    """Hurt the victim: emit the injury (and any forced change); return the stoppage seconds.

    A player who cannot continue is replaced from the bench when a change is allowed; otherwise
    the side plays short, unless it is already at the minimum, in which case he limps on.
    """
    state, victim = play.state, incident.victim
    team = state.team(victim.side)
    kind = _pick_type(play, incident.cause)
    stoppage = _stoppage_s(play, kind.severity)
    replacement = None
    wants_off = _wants_off(play, kind.severity)
    if wants_off and can_change(team, state.elapsed_s, Window.FORCED, play.cfg.manager):
        replacement = replacement_for(team, victim)
    leaves = wants_off and (
        replacement is not None or len(team.players) > play.cfg.discipline.min_players
    )
    if leaves and replacement is None:
        _leave_short(play, victim)
    _emit_injury(play, incident, kind, stoppage, leaves=leaves)
    state.injury_log.append(
        InjuryCase(
            victim.player_id, victim.side, kind.name, kind.body_part, kind.severity, state.elapsed_s
        )
    )
    state.stoppage_s += stoppage
    if replacement is not None:
        stoppage += make_substitution(play, victim, replacement, "injury", Window.FORCED)
    return stoppage


def _hurt_by(play: Play, victim: PlayerState, chance: float) -> bool:
    """Roll once against the base chance scaled by the victim's hazard."""
    scale = hazard_multiplier(victim, play.state.conditions, play.cfg.injury)
    return play.injury.u() < chance * scale


def injure_in_foul(play: Play, fouler: PlayerState, fouled: PlayerState, foul_id: str) -> float:
    """Maybe hurt the fouled player; return the stoppage seconds (zero when nobody is hurt)."""
    cfg = play.cfg.injury
    if not cfg.enabled or not _hurt_by(play, fouled, cfg.foul_contact):
        return 0.0
    return injure(play, Incident(fouled, "foul", fouler, foul_id))


def injure_in_tackle(
    play: Play, tackler: PlayerState, carrier: PlayerState, tackle_id: str
) -> float:
    """Maybe hurt one of the two in a clean tackle (the tackler or the carrier, evenly)."""
    cfg = play.cfg.injury
    if not cfg.enabled:
        return 0.0
    carrier_hurt = play.injury.u() < _HALF
    victim, other = (carrier, tackler) if carrier_hurt else (tackler, carrier)
    if not _hurt_by(play, victim, cfg.tackle_contact):
        return 0.0
    return injure(play, Incident(victim, "contact", other, tackle_id))


def injure_without_contact(play: Play, dt_s: float) -> float:
    """Maybe strain a player while play runs for `dt_s` seconds; return the stoppage seconds."""
    cfg = play.cfg.injury
    if not cfg.enabled or play.injury.u() >= cfg.non_contact_per_match * dt_s / _MATCH_S:
        return 0.0
    state = play.state
    players = [*state.home.players, *state.away.players]
    weights = [hazard_multiplier(player, state.conditions, cfg) for player in players]
    victim = players[play.injury.choice_weighted(weights)]
    return injure(play, Incident(victim, "non_contact", None, None))


def injury_reports(state: MatchState) -> tuple[InjuryReport, ...]:
    """Return the true diagnosis of every in-match injury, in the order they happened.

    `expected_return_days` is the typical layoff of the injury type; the league layer scales it by
    proneness and medical staff (docs/design/02 section 9).
    """
    return tuple(
        InjuryReport(
            player_id=case.player_id,
            type=case.name,
            body_part=case.body_part,
            severity=case.severity,
            expected_return_days=base_days_of(case.name),
        )
        for case in state.injury_log
    )
