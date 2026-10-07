"""Hypothesis strategies that build valid domain graphs."""

from __future__ import annotations

import datetime as dt

from hypothesis import strategies as st

from footystreams.domain.club import (
    Board,
    Club,
    ClubColours,
    ClubLocation,
    Facilities,
    Fanbase,
    KitSpec,
    YouthAcademy,
)
from footystreams.domain.competition import Competition, MatchRules, Season
from footystreams.domain.finance import ClubFinances
from footystreams.domain.manager import (
    Manager,
    ManagerAttrs,
    ManagerStyle,
    Philosophy,
    PressProfile,
    PressTone,
    SubHabits,
    TouchlineBehaviour,
)
from footystreams.domain.person import (
    Appearance,
    Birthplace,
    Person,
    Personality,
    Pronunciation,
)
from footystreams.domain.stadium import Pitch, Stadium
from footystreams.domain.types import (
    ClubId,
    CompetitionId,
    FormationId,
    Gender,
    NationId,
    Pronouns,
    SeasonId,
)
from tests.factories.tactics import make_team_tactics

DISPOSITION = st.integers(min_value=0, max_value=100)
ATTRIBUTE = st.integers(min_value=1, max_value=100)
REPUTATION = st.integers(min_value=0, max_value=100)
UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
GAME_DATES = st.dates(min_value=dt.date(1970, 1, 1), max_value=dt.date(2010, 12, 31))
SEASON_DATES = st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2035, 12, 31))
ID_SUFFIX = st.from_regex(r"[0-9a-z]{4,12}", fullmatch=True)
NAMES = st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N")))
SHORT_CODES = st.from_regex(r"[A-Z]{3}", fullmatch=True)
INTERVIEW_STYLES = (
    "guarded",
    "candid",
    "bland",
    "combative",
    "humble",
    "cocky",
    "philosophical",
    "jokey",
)


@st.composite
def pronunciations(draw: st.DrawFn) -> Pronunciation:
    return Pronunciation(
        respelling=draw(NAMES),
        ipa=draw(st.none() | NAMES),
        stress_syllable=draw(st.integers(min_value=0, max_value=5)),
    )


@st.composite
def appearances(draw: st.DrawFn) -> Appearance:
    return Appearance(
        skin_tone=draw(st.integers(min_value=1, max_value=8)),
        hair_style=draw(NAMES),
        hair_colour=draw(NAMES),
        facial_hair=draw(NAMES),
        build=draw(NAMES),
    )


@st.composite
def personalities(draw: st.DrawFn) -> Personality:
    return Personality(
        ambition=draw(DISPOSITION),
        loyalty=draw(DISPOSITION),
        professionalism=draw(DISPOSITION),
        volatility=draw(DISPOSITION),
        sportsmanship=draw(DISPOSITION),
        ego=draw(DISPOSITION),
        sociability=draw(DISPOSITION),
        humor=draw(DISPOSITION),
        media_openness=draw(DISPOSITION),
        resilience=draw(DISPOSITION),
        archetype_tags=tuple(draw(st.lists(NAMES, max_size=3))),
        interview_style=draw(st.sampled_from(INTERVIEW_STYLES)),
    )


@st.composite
def persons(draw: st.DrawFn, *, prefix: str = "plr") -> Person:
    suffix = draw(ID_SUFFIX)
    nation = NationId(f"nat_{draw(ID_SUFFIX)}")
    return Person(
        id=f"{prefix}_{suffix}",
        first_name=draw(NAMES),
        last_name=draw(NAMES),
        known_as=draw(NAMES),
        pronunciation=draw(pronunciations()),
        gender=draw(st.sampled_from(list(Gender))),
        pronouns=draw(st.sampled_from(list(Pronouns))),
        date_of_birth=draw(GAME_DATES),
        nationality=nation,
        second_nationality=None,
        birthplace=Birthplace(city=draw(NAMES), nation=nation),
        appearance=draw(appearances()),
        personality=draw(personalities()),
        reputation=draw(REPUTATION),
    )


@st.composite
def managers(draw: st.DrawFn) -> Manager:
    person = draw(persons(prefix="mgr"))
    attrs = {name: draw(ATTRIBUTE) for name in ManagerAttrs.model_fields}
    payload = person.model_dump()
    payload.update(
        {
            "style": draw(st.sampled_from(list(ManagerStyle))),
            "philosophy": Philosophy(
                possession_preference=draw(UNIT),
                directness=draw(UNIT),
                pressing_intensity=draw(UNIT),
                tempo=draw(UNIT),
                width=draw(UNIT),
                defensive_line=draw(UNIT),
                risk_taking=draw(UNIT),
            ),
            "preferred_formation": FormationId("433"),
            "flexibility": draw(UNIT),
            "substitution_habits": SubHabits(
                earliest_minute=draw(st.integers(min_value=0, max_value=90)),
                aggressiveness=draw(UNIT),
                fresh_legs_bias=draw(UNIT),
                protect_lead_bias=draw(UNIT),
                chase_game_bias=draw(UNIT),
                reacts_to_cards=draw(UNIT),
            ),
            "touchline_behaviour": draw(st.sampled_from(list(TouchlineBehaviour))),
            "attributes": ManagerAttrs(**attrs),
            "press_style": PressProfile(
                tone=draw(st.sampled_from(list(PressTone))),
                candour=draw(UNIT),
                deflection=draw(UNIT),
                blame_tendency=draw(UNIT),
                bold_claims=draw(UNIT),
                mind_games=draw(UNIT),
                humor=draw(UNIT),
            ),
        }
    )
    return Manager.model_validate(payload)


@st.composite
def clubs(draw: st.DrawFn) -> Club:
    suffix = draw(ID_SUFFIX)
    nation = NationId(f"nat_{draw(ID_SUFFIX)}")
    reconciled = draw(SEASON_DATES)
    return Club(
        id=ClubId(f"clb_{suffix}"),
        name=draw(NAMES),
        short_name=draw(NAMES),
        short_code=draw(SHORT_CODES),
        colours=ClubColours(
            primary="#111111",
            secondary="#eeeeee",
            accent="#ff0000",
            home_kit=KitSpec(),
            away_kit=KitSpec(),
        ),
        founded_year=draw(st.integers(min_value=1800, max_value=2100)),
        location=ClubLocation(
            city=draw(NAMES),
            nation_id=nation,
            population=draw(st.integers(min_value=0, max_value=5_000_000)),
        ),
        stadium=Stadium(
            name=draw(NAMES),
            capacity=draw(st.integers(min_value=5_000, max_value=80_000)),
            pitch=Pitch(length_m=105, width_m=68, quality=draw(UNIT)),
            atmosphere=draw(UNIT),
            proximity=draw(UNIT),
        ),
        fanbase=Fanbase(
            size=draw(st.integers(min_value=0, max_value=200_000)),
            passion=draw(UNIT),
            toxicity=draw(UNIT),
            fickleness=draw(UNIT),
            away_following=draw(UNIT),
        ),
        finances=ClubFinances(
            balance=draw(st.integers(min_value=0, max_value=50_000_000)),
            wage_budget_weekly=draw(st.integers(min_value=0, max_value=1_000_000)),
            transfer_budget=draw(st.integers(min_value=0, max_value=20_000_000)),
            last_reconciled_on=reconciled,
        ),
        facilities=Facilities(
            training=draw(ATTRIBUTE),
            youth=draw(ATTRIBUTE),
            medical=draw(ATTRIBUTE),
        ),
        academy=YouthAcademy(
            level=draw(ATTRIBUTE),
            intake_size=draw(st.integers(min_value=0, max_value=10)),
            intake_quality=draw(UNIT),
        ),
        board=Board(
            ambition=draw(DISPOSITION),
            patience=draw(DISPOSITION),
            meddling=draw(DISPOSITION),
            budget_strictness=draw(DISPOSITION),
        ),
        club_reputation=draw(REPUTATION),
        default_tactics=make_team_tactics(),
    )


@st.composite
def competitions(draw: st.DrawFn) -> Competition:
    suffix = draw(ID_SUFFIX)
    club_a = ClubId(f"clb_{draw(ID_SUFFIX)}")
    club_b = ClubId(f"clb_{draw(ID_SUFFIX)}")
    return Competition(
        id=CompetitionId(f"cmp_{suffix}"),
        name=draw(NAMES),
        short_name=draw(NAMES),
        club_ids=(club_a, club_b),
        rules=MatchRules(),
    )


@st.composite
def seasons(draw: st.DrawFn) -> Season:
    start = draw(SEASON_DATES)
    end = start + dt.timedelta(days=draw(st.integers(min_value=30, max_value=300)))
    return Season(
        id=SeasonId(f"ssn_{draw(ID_SUFFIX)}"),
        competition_id=CompetitionId(f"cmp_{draw(ID_SUFFIX)}"),
        label=draw(NAMES),
        starts_on=start,
        ends_on=end,
    )
