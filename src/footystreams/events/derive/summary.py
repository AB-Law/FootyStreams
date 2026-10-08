"""Build the match summary as a pure fold over the event log.

Everything in the summary is derivable from the events (plus the setup for lineups and positions,
and the few facts the log cannot carry, passed in as `SummaryInputs`), so `verify` and `analytics`
recompute it and compare (invariant M14).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from footystreams.domain.match import MatchSetup, SetupRef, TeamSheet
from footystreams.domain.types import PlayerId
from footystreams.events.clock import period_elapsed_s
from footystreams.events.derive.hooks import narrative_hooks
from footystreams.events.derive.maps import (
    key_moments,
    momentum_timeline,
    pass_matrix,
    shot_map,
    xg_timeline,
    zone_pass_flow,
)
from footystreams.events.derive.presence import Spell, injured_players, player_spells
from footystreams.events.derive.ratings import player_of_the_match, rate_match
from footystreams.events.derive.tally import PlayerTally, SideTally, Tally, tally_events
from footystreams.events.open_play import GoalEvent
from footystreams.events.structure import FrameEvent, HalftimeEvent
from footystreams.events.summary import MatchSummary, PlayerMatchStats, TeamStats
from footystreams.events.summary_rows import InjuryReport
from footystreams.events.types import MatchEvent

_ROUND = 4


@dataclass(frozen=True, slots=True)
class SummaryInputs:
    """What goes into the summary beside the events: run identity and facts the log omits."""

    seed: int
    config_hash: str
    log_digest: str
    injuries: tuple[InjuryReport, ...] = ()  # the true diagnoses (the events show symptoms)
    end_exhaustion: Mapping[PlayerId, float] = field(default_factory=dict)


def match_duration_s(events: Sequence[MatchEvent]) -> int:
    """Return the playing seconds of the match: the last event of each period, summed."""
    last_per_period: dict[int, int] = {}
    for event in events:
        last_per_period[event.clock.period] = period_elapsed_s(event.clock)
    return sum(last_per_period.values())


def halftime_score(events: Sequence[MatchEvent]) -> tuple[int, int]:
    """Return the score at the halftime event, or (0, 0) when there was none."""
    for event in events:
        if isinstance(event, HalftimeEvent):
            return event.score_home, event.score_away
    return 0, 0


def _team_stats(side: SideTally, other: SideTally) -> TeamStats:
    total = side.possession_s + other.possession_s
    final_third = side.final_third_passes + other.final_third_passes
    return TeamStats(
        possession=round(side.possession_s / total, _ROUND) if total else 0.5,
        shots=side.shots,
        shots_on_target=side.on_target,
        xg=round(side.xg, _ROUND),
        passes=side.passes,
        pass_accuracy=round(side.completed / side.passes, _ROUND) if side.passes else 0.0,
        fouls=side.fouls,
        corners=side.corners,
        yellows=side.yellows,
        reds=side.reds,
        key_passes=side.key_passes,
        dribbles=side.dribbles,
        dribbles_won=side.dribbles_won,
        tackles=side.tackles,
        tackles_won=side.tackles_won,
        interceptions=side.interceptions,
        clearances=side.clearances,
        offsides=side.offsides,
        saves=side.saves,
        big_chances=side.big_chances,
        xt=round(side.xt, _ROUND),
        field_tilt=round(side.final_third_passes / final_third, _ROUND) if final_third else 0.5,
    )


def _position_of(sheet: TeamSheet, player_id: PlayerId) -> str:
    competence = sheet.squad[player_id].position_competence
    if not competence:
        return ""
    best = max(competence, key=lambda position: (competence[position], str(position)))
    return str(best)


@dataclass(frozen=True, slots=True)
class _SideContext:
    """What a player row needs about his side."""

    sheet: TeamSheet
    conceded: int
    tally: Tally
    spells: Mapping[PlayerId, Spell]
    inputs: SummaryInputs
    injured: frozenset[PlayerId]


def _row(player_id: PlayerId, side: _SideContext) -> PlayerMatchStats:
    spell, counted = side.spells[player_id], side.tally.players.get(player_id, PlayerTally())
    return PlayerMatchStats(
        player_id=player_id,
        minutes=spell.minutes,
        goals=counted.goals,
        assists=counted.assists,
        shots=counted.shots,
        xg=round(counted.xg, _ROUND),
        yellows=counted.yellows,
        reds=counted.reds,
        starts=spell.started,
        position=_position_of(side.sheet, player_id),
        shots_on_target=counted.on_target,
        xa=round(counted.xa, _ROUND),
        xt=round(counted.xt, _ROUND),
        passes=counted.passes,
        passes_completed=counted.completed,
        key_passes=counted.key_passes,
        progressive_passes=counted.progressive,
        dribbles=counted.dribbles,
        dribbles_won=counted.dribbles_won,
        tackles=counted.tackles,
        tackles_won=counted.tackles_won,
        interceptions=counted.interceptions,
        clearances=counted.clearances,
        fouls=counted.fouls,
        fouled=counted.fouled,
        saves=counted.saves,
        goals_conceded=counted.goals_conceded,
        clean_sheet=side.conceded == 0 and spell.minutes >= CLEAN_SHEET_MINUTES,
        end_exhaustion=side.inputs.end_exhaustion.get(player_id, 0.0),
        injured=player_id in side.injured,
    )


CLEAN_SHEET_MINUTES = 60


def _player_rows(
    setup: MatchSetup,
    tally: Tally,
    spells: Mapping[PlayerId, Spell],
    inputs: SummaryInputs,
    injured: frozenset[PlayerId],
) -> tuple[PlayerMatchStats, ...]:
    rows: list[PlayerMatchStats] = []
    for sheet, side in ((setup.home, tally.home), (setup.away, tally.away)):
        context = _SideContext(sheet, side.conceded, tally, spells, inputs, injured)
        played = sorted(
            (pid for pid in sheet.squad if pid in spells),
            key=lambda pid: (spells[pid].start_s, not spells[pid].started, pid),
        )
        rows.extend(_row(pid, context) for pid in played)
    return tuple(rows)


def build_summary(
    events: Sequence[MatchEvent], setup: MatchSetup, inputs: SummaryInputs
) -> MatchSummary:
    """Fold the events (everything before the summary event) into a `MatchSummary`.

    Tracking frames are ignored: a log with frames summarises exactly like one without.
    """
    events = [event for event in events if not isinstance(event, FrameEvent)]
    tally = tally_events(events, setup)
    duration = match_duration_s(events)
    ht_home, ht_away = halftime_score(events)
    score_home = sum(isinstance(e, GoalEvent) and e.team == "home" for e in events)
    score_away = sum(isinstance(e, GoalEvent) and e.team == "away" for e in events)
    spells = player_spells(events, setup, duration)
    rows = _player_rows(setup, tally, spells, inputs, injured_players(events))
    sides = dict.fromkeys(setup.home.squad, "home") | dict.fromkeys(setup.away.squad, "away")
    ratings = rate_match(rows, sides, score_home - score_away)
    rated = tuple(
        row.model_copy(update={"rating": rating.rating})
        for row, rating in zip(rows, ratings, strict=True)
    )
    teams = (_team_stats(tally.home, tally.away), _team_stats(tally.away, tally.home))
    return MatchSummary(
        config_hash=inputs.config_hash,
        seed=inputs.seed,
        log_digest=inputs.log_digest,
        score_home=score_home,
        score_away=score_away,
        ht_home=ht_home,
        ht_away=ht_away,
        attendance=setup.attendance,
        duration_s=duration,
        team_stats_home=teams[0],
        team_stats_away=teams[1],
        player_stats=rated,
        ratings=ratings,
        player_of_the_match=player_of_the_match(rows, ratings),
        injuries=inputs.injuries,
        hooks=narrative_hooks(events, rated, teams, is_derby=setup.is_derby),
        momentum_timeline=momentum_timeline(events, duration),
        xg_timeline=xg_timeline(events),
        key_moments=key_moments(events),
        pass_matrix=pass_matrix(events),
        zone_pass_flow=zone_pass_flow(events),
        shot_map=shot_map(events),
    )


def setup_ref(setup: MatchSetup) -> SetupRef:
    """Return the lightweight identity of a setup for the `MatchResult`."""
    return SetupRef(
        match_id=setup.match_id,
        home_club_id=setup.home.club.id,
        away_club_id=setup.away.club.id,
        fixture_id=setup.fixture_id,
    )
