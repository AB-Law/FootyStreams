"""Fact briefs for a match: the preview before it and the recap after it."""

from __future__ import annotations

from pydantic import JsonValue

from footystreams.domain.match import MatchSetup
from footystreams.events.summary import MatchSummary
from footystreams.extensions.brief import BroadcastBrief
from footystreams.extensions.pack import pack_broadcast_brief
from footystreams.extensions.show.bible import Result, Scorer, ShowBible
from footystreams.extensions.show.facts import derby_facts, standing_facts
from footystreams.extensions.show.ledger import form, meetings, scoreline
from footystreams.extensions.show.models import Screen, ScreenRow
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.plan import Plan
from footystreams.extensions.show.schedule import fixture_key, show_date
from footystreams.extensions.show.segment_brief import SegmentBrief

MOMENTS_SHOWN = 6
SECONDS_PER_MINUTE = 60
_DROPPED = {"crew", "match_id", "key_moments", "hooks"}


def _pack(room: Newsroom, setup: MatchSetup, summary: MatchSummary | None) -> BroadcastBrief:
    return pack_broadcast_brief(room.world, setup, summary)


def _names(room: Newsroom, brief: BroadcastBrief) -> list[str]:
    names = [brief.home.name, brief.away.name, room.clubs[brief.home.id].stadium.name]
    names += [label for label in (brief.home.rivalry_label, brief.away.rivalry_label) if label]
    names += [manager.known_as for manager in (brief.home_manager, brief.away_manager) if manager]
    names += [person.known_as for person in brief.players]
    names += [
        line.club_name for person in brief.players for line in person.career if line.club_name
    ]
    names += [
        line.club_name
        for m in (brief.home_manager, brief.away_manager)
        if m
        for line in m.career
        if line.club_name
    ]
    if brief.score and brief.score.potm_name:
        names.append(brief.score.potm_name)
    return names


def _pairing_facts(room: Newsroom, bible: ShowBible, plan: Plan) -> dict[str, JsonValue]:
    pairing = plan.fixture()
    home, away = room.clubs[pairing.home_id], room.clubs[pairing.away_id]
    return {
        "matchday": pairing.matchday,
        "season": plan.season,
        "home": {**standing_facts(room, bible, pairing.home_id), "club": home.name},
        "away": {**standing_facts(room, bible, pairing.away_id), "club": away.name},
        "derby": derby_facts(room, home)
        if any(r.club_id == away.id for r in home.rivalries)
        else {},
        "earlier_meetings_on_the_desk": [
            scoreline(r) for r in meetings(bible.results, pairing.home_id, pairing.away_id)
        ],
    }


def preview_brief(room: Newsroom, bible: ShowBible, plan: Plan, setup: MatchSetup) -> SegmentBrief:
    """The match about to be played: form, history between the clubs, and who is in it."""
    pairing = plan.fixture()
    brief = _pack(room, setup, None)
    facts: dict[str, JsonValue] = {
        "fixture": _pairing_facts(room, bible, plan),
        "match_pack": brief.model_dump(
            mode="json", exclude=_DROPPED | {"score", "team_stats_note"}
        ),
    }
    home, away = room.clubs[pairing.home_id], room.clubs[pairing.away_id]
    results = bible.results
    return SegmentBrief(
        title=f"Next up: {home.name} v {away.name}",
        label="Next match",
        goal=(
            f"Preview {home.name} against {away.name}: the form, the history between them, the "
            "people to watch. Every host commits to a pick for the result and defends it."
        ),
        facts=facts,
        names=tuple(dict.fromkeys(_names(room, brief))),
        topics=(pairing.home_id, pairing.away_id),
        screen=Screen(
            kind="card",
            title="FORM GUIDE",
            rows=(
                ScreenRow(
                    label=home.short_name[:22], value=form(results, pairing.home_id) or "NEW"
                ),
                ScreenRow(
                    label=away.short_name[:22], value=form(results, pairing.away_id) or "NEW"
                ),
            ),
        ),
        ask_predictions=True,
    )


def result_of(room: Newsroom, plan: Plan, summary: MatchSummary) -> Result:
    """The result to book once the recap has aired: score, scorers and player of the match."""
    pairing = plan.fixture()
    scorers = tuple(
        Scorer(
            player_id=str(row.player_id),
            name=room.players[str(row.player_id)].known_as,
            goals=row.goals,
        )
        for row in summary.player_stats
        if row.goals > 0 and str(row.player_id) in room.players
    )
    potm = summary.player_of_the_match
    return Result(
        fixture_key=fixture_key(plan.season, pairing.index),
        season=plan.season,
        matchday=pairing.matchday,
        date=show_date(room.world.created_in_world, plan.season, pairing.matchday).isoformat(),
        home_id=pairing.home_id,
        away_id=pairing.away_id,
        home_name=room.club_names[pairing.home_id],
        away_name=room.club_names[pairing.away_id],
        home_goals=summary.score_home,
        away_goals=summary.score_away,
        potm=room.players[str(potm)].known_as if potm and str(potm) in room.players else "",
        potm_id=str(potm) if potm and str(potm) in room.players else "",
        scorers=scorers,
    )


def _assists(room: Newsroom, summary: MatchSummary) -> list[JsonValue]:
    return [
        {"player": room.players[str(row.player_id)].known_as, "assists": row.assists}
        for row in summary.player_stats
        if row.assists > 0 and str(row.player_id) in room.players
    ]


def _settled(bible: ShowBible, result: Result) -> list[JsonValue]:
    wording = {
        "home": f"{result.home_name} to win",
        "away": f"{result.away_name} to win",
        "draw": "a draw",
    }
    return [
        {
            "host": pick.host_name,
            "predicted": wording[pick.pick],
            "was_right": pick.pick == result.outcome(),
        }
        for pick in bible.predictions
        if pick.fixture_key == result.fixture_key
    ]


def _moments(summary: MatchSummary) -> list[JsonValue]:
    best = sorted(summary.key_moments, key=lambda m: (-m.significance, m.t))[:MOMENTS_SHOWN]
    return [
        f"{m.kind} in minute {m.t // SECONDS_PER_MINUTE + 1}"
        for m in sorted(best, key=lambda m: m.t)
    ]


def recap_brief(
    room: Newsroom, bible: ShowBible, plan: Plan, setup: MatchSetup, summary: MatchSummary
) -> SegmentBrief:
    """The match just played: score, scorers, key moments, and what it did to the table."""
    pairing = plan.fixture()
    result = result_of(room, plan, summary)
    after = bible.model_copy(update={"results": (*bible.results, result)})
    brief = _pack(room, setup, summary)
    facts: dict[str, JsonValue] = {
        "result": scoreline(result),
        "half_time": f"{summary.ht_home}-{summary.ht_away}",
        "scorers": [{"player": s.name, "goals": s.goals} for s in result.scorers],
        "assists": _assists(room, summary),
        "player_of_the_match": result.potm,
        "key_moments": _moments(summary),
        "fixture": _pairing_facts(room, after, plan),
        "predictions_settled": _settled(bible, result),
        "match_pack": brief.model_dump(mode="json", exclude=_DROPPED),
    }
    names = _names(room, brief) + [s.name for s in result.scorers]
    return SegmentBrief(
        title=scoreline(result),
        teaser=f"Match report: {result.home_name} v {result.away_name}",
        label="Match report",
        goal=(
            f"Recap {scoreline(result)}: how it was decided, the scorers, the player of the match "
            "and what it means for the table. Settle the predictions: gloat or squirm."
        ),
        facts=facts,
        names=tuple(dict.fromkeys(names)),
        topics=(pairing.home_id, pairing.away_id),
        screen=Screen(
            kind="score",
            title="FULL TIME",
            rows=(
                ScreenRow(label=result.home_name[:22], value=str(result.home_goals)),
                ScreenRow(label=result.away_name[:22], value=str(result.away_goals)),
            ),
        ),
        result=result,
    )
