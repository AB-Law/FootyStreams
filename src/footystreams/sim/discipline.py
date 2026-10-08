"""Fouls: how likely a challenge is foul-worthy, how bad, and whether the referee calls it.

Pure decision functions plus `roll_contact`, which draws from the `discipline` stream only
(docs/design/02 section 6): `p_foul = base x (0.6 + 0.8 aggression + 0.5 dirtiness - 0.5 tackling)
x tackling style x derby`, then the referee's call from `sim/referee.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.sim.actions.shooting import geometry_xg
from footystreams.sim.config import DisciplineConfig, RefereeConfig, ShotConfig
from footystreams.sim.effective import Skills
from footystreams.sim.geometry import CENTRE, frame_coordinate, in_penalty_area
from footystreams.sim.mathx import PERCENT, clamp
from footystreams.sim.play import Play
from footystreams.sim.referee import crowd_pressure, home_tilt, is_called
from footystreams.sim.state import PlayerState
from footystreams.sim.tactics_view import TacticsView

SeverityLabel = Literal["careless", "reckless", "violent"]
_BASE_FACTOR = 0.6  # foul-proneness of an average man is 0.6 + 0.4 + 0.25 - 0.25 = 1.0


@dataclass(frozen=True, slots=True)
class Contact:
    """A called foul: how bad it was and the facts the referee and cards depend on."""

    severity: float  # 0-1
    label: SeverityLabel
    in_box: bool  # inside the penalty area of the fouling team
    denies_opportunity: bool  # fouled man was through on goal


def contact_probability(
    tackler: Skills, view: TacticsView, *, derby: bool, cfg: DisciplineConfig, booked: bool = False
) -> float:
    """Return the chance a challenge by this man involves foul-worthy contact.

    A player who already holds a yellow card is more careful (`booked_caution`).
    """
    proneness = (
        _BASE_FACTOR
        + cfg.aggression_weight * tackler.aggression / PERCENT
        + cfg.dirtiness_weight * tackler.dirtiness / PERCENT
        - cfg.tackling_weight * tackler.tackling / PERCENT
    )
    derby_factor = cfg.derby_factor if derby else 1.0
    caution = cfg.booked_caution if booked else 1.0
    chance = cfg.contact_base * proneness * view.tackle_aggression * derby_factor * caution
    return clamp(chance, 0.0, 1.0)


def severity_of(tackler: Skills, draw: float, cfg: DisciplineConfig) -> float:
    """Return a foul's severity in [0, 1] from a uniform draw and the man's temper."""
    raw = (
        cfg.severity_base
        + cfg.severity_spread * draw
        + cfg.severity_aggression * tackler.aggression / PERCENT
        + cfg.severity_dirtiness * tackler.dirtiness / PERCENT
        - (cfg.severity_aggression + cfg.severity_dirtiness) / 2.0
    )
    return clamp(raw, 0.0, 1.0)


def severity_label(severity: float, cfg: DisciplineConfig) -> SeverityLabel:
    """Name a severity: careless, reckless or violent."""
    if severity < cfg.careless_max:
        return "careless"
    return "reckless" if severity < cfg.reckless_max else "violent"


def denies_opportunity(
    carrier: PlayerState,
    opponents: list[PlayerState],
    rules: tuple[DisciplineConfig, ShotConfig],
    direction: int,
) -> bool:
    """True when the fouled man had a clear chance: through on goal and close enough to score.

    Through on goal is far up the pitch with at most the keeper ahead; a clear chance is also an
    unpressured xG of `dogso_min_xg` from where he stood, so a wide or distant run past the last
    defender is not a denied goal (M8: it made 1.4 reds a match against about 0.1 in a league).
    """
    cfg, shot = rules
    fx = frame_coordinate(carrier.x, direction)
    if fx < cfg.dogso_min_frame_x:
        return False
    ahead = sum(frame_coordinate(opponent.x, direction) > fx for opponent in opponents)
    if ahead > cfg.dogso_max_defenders_ahead:
        return False
    return geometry_xg(fx, frame_coordinate(carrier.y, direction), shot) >= cfg.dogso_min_xg


def box_shift(profile_penalty_propensity: float, cfg: RefereeConfig) -> float:
    """Return how much a contact in the box needs extra severity to be whistled.

    `box_leniency` makes every referee reluctant; a penalty-prone referee (propensity above 0.5)
    is less so.
    """
    return cfg.box_leniency - cfg.penalty_swing * (profile_penalty_propensity - CENTRE) * 2.0


def roll_contact(play: Play, tackler: PlayerState, carrier: PlayerState) -> Contact | None:
    """Roll for a called foul in a challenge; None when there is no contact or the referee waves on.

    Consumes one draw, plus (when there is contact) one for severity and the referee's call.
    """
    state, cfg = play.state, play.cfg
    fouling_team = state.team(tackler.side)
    attack_dir = state.team(carrier.side).attack_dir
    in_box = in_penalty_area(
        frame_coordinate(carrier.x, attack_dir), frame_coordinate(carrier.y, attack_dir)
    )
    chance = contact_probability(
        tackler.skills,
        fouling_team.view,
        derby=state.is_derby,
        cfg=cfg.discipline,
        booked=tackler.yellow_cards > 0,
    )
    if in_box:
        chance *= cfg.discipline.box_caution
    if play.discipline.u() >= chance:
        return None
    severity = severity_of(tackler.skills, play.discipline.u(), cfg.discipline)
    crowd = crowd_pressure(state.attendance, cfg.referee)
    tilt = home_tilt(play.referee, tackler.side, crowd, cfg.referee)
    if in_box:
        tilt -= box_shift(play.referee.penalty_propensity, cfg.referee)
    if not is_called(play.referee, severity, tilt, cfg.referee, play.discipline):
        return None
    return Contact(
        severity,
        severity_label(severity, cfg.discipline),
        in_box,
        denies_opportunity(carrier, fouling_team.players, (cfg.discipline, cfg.shot), attack_dir),
    )
