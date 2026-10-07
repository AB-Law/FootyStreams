"""Draw the incidents (goals, cards, injuries) of a result-only match."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.rng import WorldRng
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import PlayerId, Position
from footystreams.league.config import ResultOnlyConfig
from footystreams.league.result_events import MATCH_MINUTES, SECONDS_PER_MINUTE, Draft, Kind, Side

ASSIST_CHANCE = 0.75
DEFAULT_FINISHING = 50
FINISHING_REFERENCE = 50.0
SCORER_WEIGHT: Mapping[Position, float] = {
    Position.ST: 6.0, Position.SS: 5.0, Position.RW: 3.5, Position.LW: 3.5, Position.AM: 3.0,
    Position.RM: 2.5, Position.LM: 2.5, Position.CM: 1.5, Position.DM: 0.8, Position.RWB: 0.9,
    Position.LWB: 0.9, Position.RB: 0.7, Position.LB: 0.7, Position.CB: 0.6, Position.GK: 0.02,
}  # fmt: skip


def primary_position(snapshot: PlayerSnapshot) -> Position:
    """The position the player is most competent at (ties broken by the position order)."""
    return max(
        snapshot.position_competence, key=lambda pos: (snapshot.position_competence[pos], pos)
    )


def _scoring_weight(snapshot: PlayerSnapshot) -> float:
    finishing = snapshot.technical.finishing or DEFAULT_FINISHING
    return SCORER_WEIGHT[primary_position(snapshot)] * finishing / FINISHING_REFERENCE


def _moment(rng: WorldRng) -> tuple[int, int]:
    tick = rng.randint(1, MATCH_MINUTES * SECONDS_PER_MINUTE - 1)
    return divmod(tick, SECONDS_PER_MINUTE)


def _discipline(
    rng: WorldRng, side: Side, starters: Sequence[PlayerSnapshot], config: ResultOnlyConfig
) -> list[Draft]:
    """Yellow cards, red cards and injuries: one independent chance per starter and kind."""
    chances: tuple[tuple[Kind, float], ...] = (
        ("yellow", config.yellow_chance),
        ("red", config.red_chance),
        ("injury", config.injury_chance),
    )
    drafts: list[Draft] = []
    for player in starters:
        for kind, chance in chances:
            if rng.bernoulli(chance):
                minute, second = _moment(rng)
                drafts.append(Draft(minute, second, side, kind, player.id))
    return drafts


def _scorer_pool(
    starters: Sequence[PlayerSnapshot], drafts: Sequence[Draft], minute: int
) -> dict[PlayerId, float]:
    gone = {d.player for d in drafts if d.kind == "red" and d.minute < minute}
    return {p.id: _scoring_weight(p) for p in starters if p.id not in gone}


def _goal(
    rng: WorldRng, side: Side, starters: Sequence[PlayerSnapshot], earlier: Sequence[Draft]
) -> Draft:
    minute, second = _moment(rng)
    pool = _scorer_pool(starters, earlier, minute) or {p.id: 1.0 for p in starters}
    scorer = rng.choice_weighted(pool)
    mates = {pid: weight for pid, weight in pool.items() if pid != scorer}
    assist = rng.choice_weighted(mates) if mates and rng.bernoulli(ASSIST_CHANCE) else None
    return Draft(minute, second, side, "goal", scorer, assist)


def draw_side(
    rng: WorldRng,
    side: Side,
    starters: Sequence[PlayerSnapshot],
    goals: int,
    config: ResultOnlyConfig,
) -> list[Draft]:
    """All incidents of one side: discipline first, then ``goals`` goals by players still on."""
    drafts = _discipline(rng.fork("discipline"), side, starters, config)
    scoring = rng.fork("goals")
    drafts.extend(_goal(scoring, side, starters, drafts) for _ in range(goals))
    return drafts
