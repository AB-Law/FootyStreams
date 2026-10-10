"""Fact briefs for the segments that are not about a match: history, stories, table, banter."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import JsonValue

from footystreams.domain.club import Club
from footystreams.extensions.brief import CareerLine
from footystreams.extensions.pack import manager_career_line, player_career_line
from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.ledger import (
    biggest_win,
    form,
    position,
    scoreline,
    season_results,
    table,
    top_scorers,
)
from footystreams.extensions.show.models import Screen, ScreenRow
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.segment_brief import SegmentBrief

TABLE_ROWS_SHOWN = 5
RECENT_RESULTS = 3
CARD_VALUE = 20
LABELS = {
    "club_history": "Club history",
    "manager_story": "Manager file",
    "player_story": "Player file",
    "banter": "Desk chat",
    "table_talk": "The table",
}


def career_facts(lines: Sequence[CareerLine]) -> list[JsonValue]:
    """Career stints as speakable facts."""
    return [
        {
            "club": line.club_name or "a club outside the league",
            "from": line.from_year,
            "to": line.to_year,
            "record": line.detail,
        }
        for line in lines
    ]


def standing_facts(room: Newsroom, bible: ShowBible, club_id: str) -> dict[str, JsonValue]:
    """Where a club stands on the desk table this season, and how it has been playing."""
    results = season_results(bible.results, bible.season)
    played = [r for r in results if club_id in (r.home_id, r.away_id)]
    facts: dict[str, JsonValue] = {"season": bible.season, "matches_aired": len(played)}
    if played:
        rows = table(results, room.club_names)
        facts["table_position"] = position(rows, club_id)
        facts["form_oldest_first"] = form(results, club_id)
        facts["latest_results"] = [scoreline(r) for r in played[-RECENT_RESULTS:]]
    return facts


def derby_facts(room: Newsroom, club: Club) -> dict[str, JsonValue]:
    """The club's fiercest rivalry, with its origin story, or nothing."""
    if not club.rivalries:
        return {}
    rival = max(club.rivalries, key=lambda row: row.intensity)
    other = room.club_names.get(str(rival.club_id), "")
    return {"label": rival.label, "origin": rival.origin, "rival": other}


def _card(title: str, rows: Sequence[tuple[str, str]]) -> Screen:
    return Screen(
        kind="card",
        title=title.upper()[:40],
        rows=tuple(ScreenRow(label=label, value=value[:CARD_VALUE]) for label, value in rows),
    )


def club_history_brief(room: Newsroom, bible: ShowBible, club_id: str) -> SegmentBrief:
    """A club's identity and its record on the desk."""
    club = room.clubs[club_id]
    manager = room.manager_of(club_id)
    derby = derby_facts(room, club)
    facts: dict[str, JsonValue] = {
        "club": club.name,
        "nickname": club.nickname,
        "city": club.location.city,
        "founded_year": club.founded_year,
        "ground": club.stadium.name,
        "ground_capacity": club.stadium.capacity,
        "crest": club.crest_description,
        "culture": list(club.culture.tags),
        "manager": manager.known_as if manager else "",
        "derby": derby,
        "on_the_desk": standing_facts(room, bible, club_id),
    }
    names = [club.name, club.short_name, club.stadium.name, str(derby.get("rival", ""))]
    names += [manager.known_as] if manager else []
    return SegmentBrief(
        title=f"{club.name}: the story so far",
        label=LABELS["club_history"],
        goal=(
            f"Tell the story of {club.name}: where it comes from, its ground, its character and "
            "its rivalry, and how its season has gone on the desk. Hosts react and disagree."
        ),
        facts=facts,
        names=tuple(name for name in names if name),
        topics=(club_id,),
        screen=_card(
            club.short_name,
            [
                ("Founded", str(club.founded_year)),
                ("Ground", club.stadium.name),
                ("Nickname", club.nickname),
            ],
        ),
    )


def manager_story_brief(room: Newsroom, bible: ShowBible, manager_id: str) -> SegmentBrief:
    """A manager's career and how they are doing at their club on the desk."""
    manager = room.managers[manager_id]
    club = next((c for c in room.clubs.values() if str(c.manager_id) == manager_id), None)
    career = [manager_career_line(stint, room.wider) for stint in manager.career_history]
    facts: dict[str, JsonValue] = {
        "manager": manager.known_as,
        "style": manager.style.value,
        "press_tone": manager.press_style.tone.value,
        "club": club.name if club else "no club at the moment",
        "career": career_facts(career),
        "club_on_the_desk": standing_facts(room, bible, str(club.id)) if club else {},
    }
    names = [manager.known_as, club.name if club else ""]
    names += [line.club_name or "" for line in career]
    return SegmentBrief(
        title=f"Manager file: {manager.known_as}",
        label=LABELS["manager_story"],
        goal=(
            f"Talk about {manager.known_as}: the style, the press conferences, the career so far "
            "and how the current job is going. Good-natured needling is welcome."
        ),
        facts=facts,
        names=tuple(name for name in names if name),
        topics=(manager_id, *([str(club.id)] if club else [])),
        screen=_card(
            manager.known_as,
            [
                ("Style", manager.style.value.replace("_", " ")),
                ("Club", club.short_name if club else "-"),
                ("Spells", str(len(career))),
            ],
        ),
    )


def player_story_brief(room: Newsroom, bible: ShowBible, player_id: str) -> SegmentBrief:
    """A player's career, and what they have done on the desk."""
    player = room.players[player_id]
    club = room.clubs.get(room.club_of_player.get(player_id, ""))
    career = [player_career_line(stint, room.wider) for stint in player.career_history]
    goals = sum(
        scorer.goals
        for result in season_results(bible.results, bible.season)
        for scorer in result.scorers
        if scorer.player_id == player_id
    )
    position_name = player.primary_position.value.replace("_", " ")
    facts: dict[str, JsonValue] = {
        "player": player.known_as,
        "age": player.age_on(bible.today),
        "position": position_name,
        "club": club.name if club else "",
        "career": career_facts(career),
        "goals_on_the_desk_this_season": goals,
    }
    names = [player.known_as, club.name if club else ""] + [line.club_name or "" for line in career]
    return SegmentBrief(
        title=f"Player file: {player.known_as}",
        label=LABELS["player_story"],
        goal=(
            f"Talk about {player.known_as}: the route into this club, the career so far and what "
            "the desk has seen of them. Be specific, then be funny."
        ),
        facts=facts,
        names=tuple(name for name in names if name),
        topics=(player_id, *([str(club.id)] if club else [])),
        screen=_card(
            player.known_as,
            [
                ("Position", position_name),
                ("Club", club.short_name if club else "-"),
                ("Spells", str(len(career))),
            ],
        ),
    )


def table_brief(room: Newsroom, bible: ShowBible) -> SegmentBrief:
    """The desk table for the season so far, with the leaders and the story of the matchday."""
    results = season_results(bible.results, bible.season)
    rows = table(results, room.club_names)
    listed: list[JsonValue] = [
        {
            "position": index,
            "club": row.name,
            "played": row.played,
            "won": row.won,
            "drawn": row.drawn,
            "lost": row.lost,
            "goal_difference": row.goal_difference,
            "points": row.points,
        }
        for index, row in enumerate(rows, start=1)
    ]
    win = biggest_win(results)
    scorers = top_scorers(results)
    facts: dict[str, JsonValue] = {
        "season": bible.season,
        "matches_aired": len(results),
        "table": listed,
        "top_scorers": [{"player": name, "goals": goals} for name, goals in scorers],
        "biggest_win": scoreline(win) if win else "",
    }
    shown = rows[:TABLE_ROWS_SHOWN]
    return SegmentBrief(
        title=f"The table after {len(results)} matches",
        label=LABELS["table_talk"],
        goal=(
            "Go through the table: who leads, who is struggling, the best and worst form and "
            "the scorers. Each host has a favourite and a grudge."
        ),
        facts=facts,
        names=tuple(row.name for row in rows) + tuple(name for name, _ in scorers),
        topics=tuple(row.club_id for row in shown),
        screen=Screen(
            kind="table",
            title="THE TABLE",
            rows=tuple(ScreenRow(label=row.name[:22], value=f"{row.points} pts") for row in shown),
        ),
    )


def banter_brief(room: Newsroom, bible: ShowBible) -> SegmentBrief:
    """Free talk between the hosts, seeded with the day football and what they remember."""
    results = season_results(bible.results, bible.season)
    rows = table(results, room.club_names)
    latest = results[-1] if results else None
    seeds: list[JsonValue] = []
    names: list[str] = []
    if latest:
        seeds.append(f"Latest result on the desk: {scoreline(latest)}")
        seeds.append(f"{rows[0].name} lead the table with {rows[0].points} points")
        names += [latest.home_name, latest.away_name, rows[0].name]
    seeds.append(
        "Anything about the hosts themselves: where they are from, what they are known for"
    )
    return SegmentBrief(
        title="Around the desk",
        label=LABELS["banter"],
        goal=(
            "The hosts talk between matches: needling each other, calling back to old jokes and "
            "predictions, riffing on the football and on themselves. Keep it light and specific."
        ),
        facts={"seeds": seeds, "season": bible.season, "matches_aired": len(results)},
        names=tuple(names),
        topics=tuple(row.club_id for row in rows[:2]) if results else (),
    )
