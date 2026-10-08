"""Turn a result-only match outcome into a typed, ordered event log and its summary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from footystreams.domain.canonical import canonical_json
from footystreams.domain.match import MatchSetup, SetupRef, TeamSheet
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase, MatchClock, Participant
from footystreams.events.context import EventContext
from footystreams.events.discipline import CardEvent, InjuryEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.result import MatchResult
from footystreams.events.structure import FulltimeEvent, HalftimeEvent, KickoffEvent
from footystreams.events.summary import (
    MatchSummary,
    MatchSummaryEvent,
    PlayerMatchStats,
    PlayerRating,
    TeamStats,
)
from footystreams.events.types import MatchEvent

MATCH_MINUTES = 90
HALF_MINUTES = 45
SECONDS_PER_MINUTE = 60
BASE_RATING = 6.0
GOAL_RATING = 1.2
ASSIST_RATING = 0.6
RED_RATING = -1.0
RATING_LOW, RATING_HIGH = 3.0, 10.0
SHOT_BASE = 5
SHOTS_PER_GOAL = 4
SHOT_ON_TARGET_SHARE = 0.4
XG_PER_SHOT = 0.11
MINUTES_PER_EXTRA_SHOT = 30
POSSESSION_SPREAD = 0.2

Side = Literal["home", "away"]
Kind = Literal["goal", "yellow", "red", "injury"]


@dataclass(frozen=True, slots=True)
class Draft:
    """A match incident before it gets a sequence number and a clock."""

    minute: int
    second: int
    team: Side
    kind: Kind
    player: PlayerId
    assist: PlayerId | None = None

    @property
    def tick(self) -> int:
        """Seconds since kickoff."""
        return self.minute * SECONDS_PER_MINUTE + self.second


def _clock(minute: int, second: int = 0) -> MatchClock:
    period = 1 if minute <= HALF_MINUTES else 2
    return MatchClock(period=period, minute=minute, second=second)


def _score_at(drafts: Sequence[Draft], minute: int) -> tuple[int, int]:
    goals = [d for d in drafts if d.kind == "goal" and d.minute <= minute]
    return sum(d.team == "home" for d in goals), sum(d.team == "away" for d in goals)


def _context(drafts: Sequence[Draft], draft: Draft) -> EventContext:
    home, away = _score_at([d for d in drafts if d.tick <= draft.tick], draft.minute)
    return EventContext(score_home=home, score_away=away)


def _fields(match_id: str, seq: int, tick: int) -> dict[str, object]:
    return {"id": f"{match_id}:{seq:05d}", "match_id": match_id, "seq": seq, "tick": tick}


def _incident(setup: MatchSetup, draft: Draft, seq: int, ctx: EventContext) -> MatchEvent:
    fields = {
        **_fields(setup.match_id, seq, draft.tick),
        "clock": _clock(draft.minute, draft.second),
        "team": draft.team,
        "ctx": ctx,
    }
    if draft.kind == "goal":
        crew = [Participant(player_id=draft.player, role="scorer")]
        if draft.assist is not None:
            crew.append(Participant(player_id=draft.assist, role="assist"))
        fields |= {
            "participants": tuple(crew),
            "scorer_id": draft.player,
            "assist_id": draft.assist,
        }
        return GoalEvent.model_validate(fields)
    fields["player_id"] = draft.player
    if draft.kind == "injury":
        return InjuryEvent.model_validate(fields)
    return CardEvent.model_validate(
        {**fields, "colour": "red" if draft.kind == "red" else "yellow"}
    )


def _structure(
    setup: MatchSetup, drafts: Sequence[Draft], seq: int, name: str, minute: int
) -> MatchEvent:
    fields = {
        **_fields(setup.match_id, seq, minute * SECONDS_PER_MINUTE),
        "clock": _clock(minute),
    }
    if name == "kickoff":
        return KickoffEvent.model_validate(fields)
    home, away = _score_at(drafts, minute)
    scores = {**fields, "score_home": home, "score_away": away}
    if name == "halftime":
        return HalftimeEvent.model_validate(scores)
    return FulltimeEvent.model_validate(scores)


def build_events(setup: MatchSetup, drafts: Sequence[Draft]) -> tuple[MatchEvent, ...]:
    """Kickoff, the incidents in clock order, half time and full time, with contiguous ``seq``."""
    ordered = sorted(drafts, key=lambda d: (d.tick, d.team, d.kind, d.player))
    first = [d for d in ordered if d.minute <= HALF_MINUTES]
    second = [d for d in ordered if d.minute > HALF_MINUTES]
    events: list[MatchEvent] = [_structure(setup, ordered, 0, "kickoff", 0)]
    for group, name, minute in (
        (first, "halftime", HALF_MINUTES),
        (second, "fulltime", MATCH_MINUTES),
    ):
        for draft in group:
            events.append(_incident(setup, draft, len(events), _context(ordered, draft)))
        events.append(_structure(setup, ordered, len(events), name, minute))
    return tuple(events)


@dataclass(slots=True)
class _Row:
    player: PlayerId
    minutes: int = MATCH_MINUTES
    goals: int = 0
    assists: int = 0
    yellows: int = 0
    reds: int = 0
    shots: int = 0


def _rows(sheet: TeamSheet, side: Side, drafts: Sequence[Draft]) -> dict[PlayerId, _Row]:
    rows = {slot.player_id: _Row(slot.player_id) for slot in sheet.lineup}
    for draft in (d for d in drafts if d.team == side):
        row = rows.get(draft.player)
        if row is None:
            continue
        if draft.kind == "goal":
            row.goals += 1
        elif draft.kind == "yellow":
            row.yellows += 1
        elif draft.kind == "red":
            row.reds += 1
            row.minutes = draft.minute
        if draft.assist in rows:
            rows[draft.assist].assists += 1
    return rows


def _rate(row: _Row, rng: WorldRng, noise: float) -> float:
    rating = BASE_RATING + GOAL_RATING * row.goals + ASSIST_RATING * row.assists
    rating += RED_RATING * row.reds + rng.normal(0.0, noise)
    return round(max(RATING_LOW, min(RATING_HIGH, rating)), 1)


def _team_stats(rows: Mapping[PlayerId, _Row], goals: int, share: float) -> TeamStats:
    shots = SHOT_BASE + SHOTS_PER_GOAL * goals
    return TeamStats(
        possession=round(share, 2),
        shots=shots,
        shots_on_target=max(goals, round(shots * SHOT_ON_TARGET_SHARE)),
        xg=round(XG_PER_SHOT * shots, 2),
        yellows=sum(row.yellows for row in rows.values()),
        reds=sum(row.reds for row in rows.values()),
    )


@dataclass(frozen=True, slots=True)
class Meta:
    """What the summary stamps on the result: who simulated it, with which configuration."""

    sim_version: str
    config_hash: str
    noise: float


def _player_stats(
    rows: Mapping[PlayerId, _Row], ratings: Mapping[PlayerId, float]
) -> tuple[PlayerMatchStats, ...]:
    return tuple(
        PlayerMatchStats(
            player_id=pid,
            minutes=row.minutes,
            goals=row.goals,
            assists=row.assists,
            shots=row.goals + row.minutes // MINUTES_PER_EXTRA_SHOT,
            yellows=row.yellows,
            reds=row.reds,
            rating=ratings[pid],
        )
        for pid, row in sorted(rows.items())
    )


def _possession(score_home: int, score_away: int) -> float:
    """The side that scores more has a little more of the ball; a draw is 50-50."""
    lead = (score_home - score_away) / (score_home + score_away + 1)
    return round(0.5 + POSSESSION_SPREAD * lead, 2)


def _summary(
    setup: MatchSetup, seed: int, drafts: Sequence[Draft], extra: tuple[Meta, WorldRng, str]
) -> MatchSummary:
    meta, rng, digest = extra
    home_rows = _rows(setup.home, "home", drafts)
    away_rows = _rows(setup.away, "away", drafts)
    rows = {**home_rows, **away_rows}
    ratings = {pid: _rate(row, rng.fork(pid), meta.noise) for pid, row in sorted(rows.items())}
    score_home, score_away = _score_at(drafts, MATCH_MINUTES)
    half_home, half_away = _score_at(drafts, HALF_MINUTES)
    share = _possession(score_home, score_away)
    return MatchSummary(
        sim_version=meta.sim_version,
        config_hash=meta.config_hash,
        seed=seed,
        log_digest=digest,
        score_home=score_home,
        score_away=score_away,
        ht_home=half_home,
        ht_away=half_away,
        attendance=setup.attendance,
        duration_s=MATCH_MINUTES * SECONDS_PER_MINUTE,
        team_stats_home=_team_stats(home_rows, score_home, share),
        team_stats_away=_team_stats(away_rows, score_away, 1 - share),
        player_stats=_player_stats(rows, ratings),
        ratings=tuple(PlayerRating(player_id=pid, rating=ratings[pid]) for pid in sorted(ratings)),
        player_of_the_match=max(sorted(ratings), key=lambda pid: ratings[pid]),
    )


def _digest(events: Sequence[EventBase]) -> str:
    payload = canonical_json([event.model_dump(mode="json") for event in events])
    return hashlib.sha256(payload.encode()).hexdigest()


def build_result(
    setup: MatchSetup, seed: int, drafts: Sequence[Draft], extra: tuple[Meta, WorldRng]
) -> MatchResult:
    """The full ``MatchResult``: events, then the summary event (digest covers events before it)."""
    events = build_events(setup, drafts)
    digest = _digest(events)
    summary = _summary(setup, seed, drafts, (extra[0], extra[1], digest))
    last = events[-1]
    closing = MatchSummaryEvent.model_validate(
        {
            **_fields(setup.match_id, len(events), last.tick),
            "clock": last.clock,
            "summary": summary,
        }
    )
    return MatchResult(
        events=(*events, closing),
        summary=summary,
        setup_ref=SetupRef(
            match_id=setup.match_id,
            home_club_id=setup.home.club.id,
            away_club_id=setup.away.club.id,
            fixture_id=setup.fixture_id,
        ),
        seed=seed,
        sim_version=extra[0].sim_version,
        config_hash=extra[0].config_hash,
        log_digest=digest,
    )
