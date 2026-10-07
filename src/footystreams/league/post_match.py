"""``derive_world_delta``: everything a finished match changes in the world, as one delta.

Pure. The runner applies the delta in the match's own transaction. Nothing here reads the clock or
a database; injuries are drawn from a stream the caller derives from the match.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.ids import derive_id
from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.match import Match, MatchSetup, MatchStatus
from footystreams.domain.mood import ModifierVisibility, StateModifier, WorldEvent
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.static_tables import InjuryCatalog
from footystreams.domain.types import EntityKind, EntityRef, Id, PlayerId
from footystreams.events.discipline import InjuryEvent
from footystreams.events.result import MatchResult
from footystreams.events.summary import PlayerMatchStats
from footystreams.league.condition import PlayedMatch, apply_match, serve_suspension
from footystreams.league.config import FinanceConfig, RecoveryConfig
from footystreams.league.delta import WorldDelta
from footystreams.league.finance import MatchRef, bonus_postings, matchday_postings
from footystreams.league.injuries import draw_injury
from footystreams.league.ledger import Posting, book
from footystreams.league.mood_config import MoodConfig
from footystreams.league.mood_rules import MatchFact, modifiers_from_match
from footystreams.league.outcome import Outcome, outcome_for
from footystreams.league.setup import TeamInputs
from footystreams.persistence.ports import StoredEvent, SummaryRecord

HAT_TRICK = 3


@dataclass(frozen=True, slots=True)
class PostMatchTables:
    """Static tables the derivation reads."""

    injuries: InjuryCatalog
    recovery: RecoveryConfig
    finance: FinanceConfig
    mood: MoodConfig


@dataclass(frozen=True, slots=True)
class PlayedFixture:
    """A fixture, the setup it was played from and its result."""

    fixture: Fixture
    setup: MatchSetup
    result: MatchResult
    teams: tuple[TeamInputs, TeamInputs]  # home, away
    today: dt.date


def match_record(played: PlayedFixture) -> Match:
    """The completed match row, holding both frozen sheets so it can be replayed."""
    setup, summary, fixture = played.setup, played.result.summary, played.fixture
    return Match(
        id=setup.match_id,
        fixture_id=fixture.id,
        competition_id=fixture.competition_id,
        season_id=fixture.season_id,
        matchday=fixture.matchday,
        date=fixture.date,
        venue_stadium_id=fixture.stadium_id,
        home_club_id=fixture.home_club_id,
        away_club_id=fixture.away_club_id,
        weather=setup.weather,
        referee_id=setup.referee_id,
        attendance=setup.attendance,
        is_derby=setup.is_derby,
        importance=setup.importance,
        home_sheet=setup.home,
        away_sheet=setup.away,
        seed=played.result.seed,
        config_hash=played.result.config_hash,
        sim_version=played.result.sim_version,
        status=MatchStatus.COMPLETED,
        home_goals=summary.score_home,
        away_goals=summary.score_away,
        ht_home=summary.ht_home,
        ht_away=summary.ht_away,
        log_digest=summary.log_digest,
    )


def stored_events(result: MatchResult) -> tuple[StoredEvent, ...]:
    """The log rows of the match, in order."""
    return tuple(
        StoredEvent(
            match_id=event.match_id, seq=event.seq, type=event.type, tick=event.tick, event=event
        )
        for event in result.events
    )


def _injured(result: MatchResult) -> list[PlayerId]:
    return sorted({e.player_id for e in result.events if isinstance(e, InjuryEvent)})


def _draw_injuries(
    team: TeamInputs,
    hurt: Sequence[PlayerId],
    today: dt.date,
    context: tuple[PostMatchTables, WorldRng],
) -> dict[PlayerId, Injury]:
    tables, rng = context
    members = {PlayerId(p.id) for p in team.squad}
    level = team.club.facilities.medical
    return {
        pid: draw_injury(today, (tables.injuries, tables.recovery, level), rng.fork(pid))
        for pid in hurt
        if pid in members
    }


def _updated_players(
    team: TeamInputs,
    stats: Mapping[PlayerId, PlayerMatchStats],
    outcome: Outcome,
    injuries: Mapping[PlayerId, Injury],
    context: tuple[RecoveryConfig, dt.date],
) -> list[Player]:
    """Players who played are updated by the match; benched and unused ones serve any ban."""
    recovery, today = context
    updated: list[Player] = []
    for player in sorted(team.squad, key=lambda item: item.id):
        pid = PlayerId(player.id)
        if pid in stats:
            played = PlayedMatch(stats[pid], outcome, injuries.get(pid))
            updated.append(apply_match(player, played, (recovery, today)))
        elif player.suspension is not None:
            updated.append(serve_suspension(player))
    return updated


def _notable(
    played: PlayedFixture,
    stats: Mapping[PlayerId, PlayerMatchStats],
    hurt: Mapping[PlayerId, Injury],
) -> list[WorldEvent]:
    """Hat-tricks and serious injuries make the news feed."""
    events: list[WorldEvent] = []
    for pid, row in sorted(stats.items()):
        if row.goals >= HAT_TRICK:
            events.append(_news(played, pid, "hat_trick", {"goals": row.goals}))
    for pid, injury in sorted(hurt.items()):
        if injury.severity in {InjurySeverity.MODERATE, InjurySeverity.SEVERE}:
            events.append(_news(played, pid, "long_injury", {"injury": injury.type}))
    return events


def _news(
    played: PlayedFixture, pid: PlayerId, kind: str, facts: Mapping[str, str | int | float | bool]
) -> WorldEvent:
    return WorldEvent(
        id=Id(derive_id("world_event", pid, played.today.isoformat(), kind, played.setup.match_id)),
        date=played.today,
        kind=kind,
        participants=(EntityRef(kind=EntityKind.PLAYER, id=Id(pid)),),
        facts={**facts, "match_id": played.setup.match_id},
        visibility=ModifierVisibility.PUBLIC,
        origin="rule",
    )


def _postings(
    played: PlayedFixture, stats: Mapping[PlayerId, PlayerMatchStats], tables: PostMatchTables
) -> list[Posting]:
    home, away = played.teams
    summary = played.result.summary
    match_id = played.setup.match_id
    outcome = outcome_for(summary.score_home, summary.score_away)
    takings = (match_id, summary.attendance, outcome)
    ref_home = MatchRef(match_id, home.club.id, played.today)
    ref_away = MatchRef(match_id, away.club.id, played.today)
    return [
        *matchday_postings(home.club, takings, played.today, tables.finance),
        *bonus_postings(home.squad, (stats, summary.score_away), ref_home),
        *bonus_postings(away.squad, (stats, summary.score_home), ref_away),
    ]


@dataclass(frozen=True, slots=True)
class SideResult:
    """What a match did to one side's people."""

    players: list[Player]
    modifiers: list[StateModifier]
    injuries: dict[PlayerId, Injury]


def _side_result(
    played: PlayedFixture,
    index: int,
    context: tuple[PostMatchTables, WorldRng],
    stats: Mapping[PlayerId, PlayerMatchStats],
) -> SideResult:
    tables, rng = context
    team = played.teams[index]
    summary = played.result.summary
    scored, conceded = (
        (summary.score_home, summary.score_away)
        if index == 0
        else (summary.score_away, summary.score_home)
    )
    outcome = outcome_for(scored, conceded)
    injuries = _draw_injuries(
        team, _injured(played.result), played.today, (tables, rng.fork(f"injuries:{team.club.id}"))
    )
    members = {PlayerId(p.id) for p in team.squad}
    facts = [
        MatchFact(pid, row.goals, row.reds, row.rating, outcome, derby=played.setup.is_derby)
        for pid, row in sorted(stats.items())
        if pid in members
    ]
    return SideResult(
        players=_updated_players(team, stats, outcome, injuries, (tables.recovery, played.today)),
        modifiers=modifiers_from_match(facts, played.setup.match_id, played.today, tables.mood),
        injuries=injuries,
    )


def derive_world_delta(played: PlayedFixture, tables: PostMatchTables, rng: WorldRng) -> WorldDelta:
    """Everything the match changes: records, log, players, money, mood and news."""
    summary = played.result.summary
    stats = {PlayerId(row.player_id): row for row in summary.player_stats}
    sides = [_side_result(played, index, (tables, rng), stats) for index in range(2)]
    clubs = {team.club.id: team.club for team in played.teams}
    money = book(clubs, _postings(played, stats, tables))
    fixture = played.fixture.model_copy(
        update={"status": FixtureStatus.PLAYED, "match_id": played.setup.match_id}
    )
    return WorldDelta(
        players=tuple(p for side in sides for p in side.players),
        clubs=money.clubs,
        modifiers=tuple(m for side in sides for m in side.modifiers),
        world_events=tuple(_notable(played, stats, {**sides[0].injuries, **sides[1].injuries})),
        fixtures=(fixture,),
        matches=(match_record(played),),
        summaries=(SummaryRecord(match_id=played.setup.match_id, summary=summary),),
        ledger=money.ledger,
        events=stored_events(played.result),
    )
