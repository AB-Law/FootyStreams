"""Breaks and flashes: slideshows of sponsor ads and the show's own numbers, with no model involved.

Everything on a break comes from the bible or a fixed bank of invented sponsors, so a break can
always be made, whatever the language model is doing. A BREAKING NEWS stinger is one flashing slide.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.feed import segment_id
from footystreams.extensions.show.ledger import scoreline, season_results, table
from footystreams.extensions.show.models import ScreenRow, Segment, SegmentKind, Slide
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.plan import Plan, Roster

AD_SECONDS = 6.0
CARD_SECONDS = 7.0
STINGER_SECONDS = 9.0
TABLE_ROWS = 6
RESULTS_SHOWN = 5


@dataclass(frozen=True, slots=True)
class Ad:
    """An invented sponsor of the channel."""

    brand: str
    slogan: str
    colour: str
    dark: str


ADS = (
    Ad("Grafters Pies", "Proper pies for proper fans", "#d9822b", "#4a250a"),
    Ad("Old Road Taxis", "We know the way to the ground", "#f2c200", "#2e2600"),
    Ad("Valmere Bank", "Your money, always at home", "#1d7a8c", "#082a33"),
    Ad("Stolen Cup Brewery", "The ale worth a feud", "#9a3a3a", "#2b0d0d"),
    Ad("Zedrov Tyres", "Grip the whole season", "#4c8a3c", "#122a0c"),
    Ad("Mid-Table Mattresses", "Sleep through the relegation fight", "#6a4fa0", "#1c1233"),
    Ad("Corner Flag Coffee", "A cup for every corner", "#b5651d", "#2c1707"),
    Ad("Final Whistle Insurance", "Covered until the very end", "#2f6fb0", "#0a1d36"),
    Ad("Back Four Builders", "Solid at the back since day one", "#8a8f99", "#1c1e22"),
    Ad("Brevane Air", "Fly to every away day", "#3aa6c9", "#0a2733"),
)


def _ad_slide(number: int, offset: int) -> Slide:
    ad = ADS[(number * 3 + offset) % len(ADS)]
    return Slide(
        kind="ad",
        title=ad.brand,
        lines=(ad.slogan,),
        accent=ad.colour,
        dark=ad.dark,
        seconds=AD_SECONDS,
    )


def _table_slide(room: Newsroom, bible: ShowBible) -> Slide | None:
    results = season_results(bible.results, bible.season)
    if not results:
        return None
    rows = table(results, room.club_names)[:TABLE_ROWS]
    return Slide(
        kind="table",
        title="The table",
        rows=tuple(ScreenRow(label=row.name, value=f"{row.points} pts") for row in rows),
        seconds=CARD_SECONDS,
    )


def _results_slide(bible: ShowBible) -> Slide | None:
    results = season_results(bible.results, bible.season)
    if not results:
        return None
    latest = tuple(scoreline(result) for result in reversed(results[-RESULTS_SHOWN:]))
    return Slide(kind="results", title="Latest results", lines=latest, seconds=CARD_SECONDS)


def _fixture_slide(room: Newsroom, roster: Roster, bible: ShowBible) -> Slide | None:
    if bible.fixture_index >= len(roster.fixtures):
        return None
    fixture = roster.fixtures[bible.fixture_index]
    names = room.club_names
    return Slide(
        kind="fixture",
        title="Next match",
        lines=(names[fixture.home_id], "v", names[fixture.away_id], f"Matchday {fixture.matchday}"),
        seconds=AD_SECONDS,
    )


def break_segment(room: Newsroom, roster: Roster, bible: ShowBible, plan: Plan) -> Segment:
    """A break: an ad, the table or the results, another ad, and what is on next."""
    cards = _table_slide(room, bible) if plan.number % 2 else _results_slide(bible)
    slides = [
        slide
        for slide in (
            _ad_slide(plan.number, 0),
            cards,
            _ad_slide(plan.number, 1),
            _fixture_slide(room, roster, bible),
        )
        if slide is not None
    ]
    return Segment(
        id=segment_id(plan.number),
        number=plan.number,
        kind=SegmentKind.BREAK,
        title="VPL News will be right back",
        teaser="Break",
        label="Break",
        slides=tuple(slides),
        duration_s=sum(slide.seconds for slide in slides),
    )


def stinger_segment(number: int, headline: str) -> Segment:
    """The BREAKING NEWS flash that goes out the moment someone asks for it."""
    slide = Slide(
        kind="breaking",
        title="Breaking news",
        lines=(headline,),
        accent="#c8102e",
        dark="#14161b",
        seconds=STINGER_SECONDS,
    )
    return Segment(
        id=segment_id(number),
        number=number,
        kind=SegmentKind.BREAK,
        title="Breaking news",
        teaser="Breaking news",
        label="Breaking news",
        slides=(slide,),
        alert=headline,
        duration_s=slide.seconds,
    )
