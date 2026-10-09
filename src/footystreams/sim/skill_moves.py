"""Skill moves: how a take-on is done, chosen from the dribbler's ability and the situation.

The move is the look of a dribble, not a change to its odds: the success roll in
`actions/resolve_dribble.py` is made first and untouched, so the balance of the match does not
move. What he tries depends on who he is (dribbling, flair, agility, balance, pace) and what is in
front of him (how close the nearest defender is, how much pressure he is under, how wide he is):
a quick winger with room knocks the ball past, a skilful man with a defender on top of him tries
something showy, and a plain player seldom tries more than a simple touch. Pure arithmetic of its
inputs; the one number that varies is a low-discrepancy sequence of the tick, so no random stream
is drawn from and no other event moves.
"""

from __future__ import annotations

from enum import StrEnum

from footystreams.sim.effective import Skills
from footystreams.sim.mathx import PERCENT, clamp

CLOSE_M = 6.0  # a defender further than this is no reason to try anything
NUTMEG_M = 3.0  # a ball between the legs needs the defender this close
_GOLDEN = 0.6180339887498949  # fractional steps of this size spread evenly over [0, 1)
_WIDE_SCALE = 2.0  # |y - centre| of 0.5 is the touchline: twice it is 0..1


class SkillMove(StrEnum):
    """How a dribbler takes on a man (None on the event means a plain run with the ball)."""

    KNOCK_PAST = "knock_past"
    STEP_OVER = "step_over"
    DRAG_BACK = "drag_back"
    CUT_INSIDE = "cut_inside"
    NUTMEG = "nutmeg"
    ROULETTE = "roulette"
    RAINBOW_FLICK = "rainbow_flick"


def skill_level(dribbler: Skills) -> float:
    """Return how skilful a dribbler is in [0, 1]: dribbling, flair and agility alike."""
    return (dribbler.dribbling + dribbler.flair + dribbler.agility) / (3.0 * PERCENT)


def move_weights(
    dribbler: Skills, defender_gap_m: float | None, pressure: float, frame_y: float
) -> dict[SkillMove | None, float]:
    """Return how likely each move (or a plain run, key None) is in this situation, unnormalised."""
    level = skill_level(dribbler)
    close = 0.0 if defender_gap_m is None else clamp(1.0 - defender_gap_m / CLOSE_M, 0.0, 1.0)
    wide = clamp(abs(frame_y - 0.5) * _WIDE_SCALE, 0.0, 1.0)
    pace = dribbler.pace / PERCENT
    flair = dribbler.flair / PERCENT
    nutmeg = close * close * flair * level * level if _gap(defender_gap_m) < NUTMEG_M else 0.0
    return {
        None: 2.0 * (1.0 - level) + 3.0 * (1.0 - close),
        SkillMove.KNOCK_PAST: 1.0 + 2.0 * pace * (1.0 - close),
        SkillMove.STEP_OVER: 3.0 * level * level * close * dribbler.agility / PERCENT,
        SkillMove.DRAG_BACK: 2.0 * level * level * close * pressure * dribbler.balance / PERCENT,
        SkillMove.CUT_INSIDE: 2.0 * level * wide * close,
        SkillMove.NUTMEG: 1.5 * nutmeg,
        SkillMove.ROULETTE: 2.0
        * level
        * level
        * close
        * dribbler.balance
        / PERCENT
        * dribbler.dribbling
        / PERCENT,
        SkillMove.RAINBOW_FLICK: level * level * level * level * flair * close,
    }


def _gap(defender_gap_m: float | None) -> float:
    return CLOSE_M * 2 if defender_gap_m is None else defender_gap_m


def choose_skill_move(
    dribbler: Skills, defender_gap_m: float | None, pressure: float, frame_y: float, tick: int
) -> SkillMove | None:
    """Pick the move a dribbler tries now, or None for a plain run with the ball."""
    weights = move_weights(dribbler, defender_gap_m, pressure, frame_y)
    pick = ((tick + 1) * _GOLDEN % 1.0) * sum(weights.values())
    running = 0.0
    for move, weight in weights.items():
        running += weight
        if pick < running:
            return move
    return None
