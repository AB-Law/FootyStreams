"""What a manager can see: the scoreline, the clock, the cards and a noisy read on tiredness.

The assessment is the AI manager's only window on the match (docs/design/02 section 11). A
manager with little tactical sense misreads how tired his players look; the truth is never
exposed. Draws come from the manager's own stream.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.types import Position
from footystreams.sim.config_manager import ManagerConfig
from footystreams.sim.rng import SimRng
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import MatchState, PlayerState

PERCENT = 100.0
SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True, slots=True)
class Assessment:
    """The manager's read of the match from his own side."""

    minute: float
    margin: int  # his goals minus theirs
    men_difference: int  # his men on the pitch minus theirs
    tired: tuple[tuple[float, PlayerState], ...]  # outfielders, most tired first (apparent)
    booked: tuple[PlayerState, ...]  # yellow-carded outfielders, most aggressive first


def assess(state: MatchState, side: Side, rng: SimRng, cfg: ManagerConfig) -> Assessment:
    """Build the manager's read for `side`; one draw per outfield player on his pitch."""
    team, rival = state.team(side), state.team(opposite(side))
    sigma = cfg.noise_scale * (1.0 - team.sheet.manager.tactical_knowledge / PERCENT)
    outfield = [player for player in team.players if player.position is not Position.GK]
    apparent = [(player.exhaustion + sigma * rng.gauss(), player) for player in outfield]
    apparent.sort(key=lambda entry: (-entry[0], entry[1].slot))
    booked = sorted(
        (player for player in outfield if player.yellow_cards > 0),
        key=lambda player: (-player.skills.aggression, player.slot),
    )
    return Assessment(
        minute=state.elapsed_s / SECONDS_PER_MINUTE,
        margin=team.score - rival.score,
        men_difference=len(team.players) - len(rival.players),
        tired=tuple(apparent),
        booked=tuple(booked),
    )
