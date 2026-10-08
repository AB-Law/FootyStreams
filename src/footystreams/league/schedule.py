"""Double round-robin scheduling: circle method, balanced home/away, derbies kept off matchday 1."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence

from footystreams.domain.fixture import Fixture
from footystreams.domain.ids import derive_id
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, CompetitionId, FixtureId, SeasonId, StadiumId
from footystreams.verify.schedule import MAX_STREAK, check_schedule

MAX_ATTEMPTS = 60
FLIP_BUDGET = 400
BYE = None

Pairing = tuple[ClubId, ClubId]
Round = list[Pairing]


class ScheduleError(RuntimeError):
    """No valid schedule was found within the attempt budget."""


def circle_rounds(clubs: Sequence[ClubId]) -> list[list[tuple[ClubId, ClubId]]]:
    """Single round robin by the circle method; with an odd number of clubs one sits out a round."""
    ring: list[ClubId | None] = list(clubs)
    if len(ring) % 2:
        ring.append(BYE)
    size = len(ring)
    rounds: list[list[tuple[ClubId, ClubId]]] = []
    for _ in range(size - 1):
        pairs = []
        for index in range(size // 2):
            left, right = ring[index], ring[size - 1 - index]
            if left is not BYE and right is not BYE:
                pairs.append((left, right))
        rounds.append(pairs)
        ring = [ring[0], ring[-1], *ring[1:-1]]
    return rounds


def _berger(rounds: Sequence[Sequence[tuple[ClubId, ClubId]]]) -> list[Round]:
    """Berger-style orientation: alternate venues so each club has at most one break per half."""
    oriented: list[Round] = []
    for number, pairs in enumerate(rounds):
        matches: Round = []
        for index, (a, b) in enumerate(pairs):
            flip = (number % 2 == 0) if index == 0 else ((number + index) % 2 == 0)
            matches.append((a, b) if flip else (b, a))
        oriented.append(matches)
    return oriented


def _mirror(first_half: Sequence[Round], order: Sequence[int]) -> list[Round]:
    """The return fixtures: round ``order[k]`` of the first half with venues swapped, k-th."""
    return [[(away, home) for home, away in first_half[index]] for index in order]


def _full(first_half: Sequence[Round], order: Sequence[int]) -> list[Round]:
    return [*first_half, *_mirror(first_half, order)]


def _streak_excess(rounds: Sequence[Round]) -> dict[ClubId, list[int]]:
    """Per club, the round indexes (0-based) that sit inside a venue streak longer than allowed."""
    venues: dict[ClubId, list[tuple[int, bool]]] = {}
    for number, matches in enumerate(rounds):
        for home, away in matches:
            venues.setdefault(home, []).append((number, True))
            venues.setdefault(away, []).append((number, False))
    excess: dict[ClubId, list[int]] = {}
    for club, sequence in venues.items():
        run: list[int] = []
        previous: bool | None = None
        for number, at_home in sequence:
            run = [*run, number] if at_home == previous else [number]
            previous = at_home
            if len(run) > MAX_STREAK:
                excess.setdefault(club, []).extend(run)
    return excess


def _cost(excess: dict[ClubId, list[int]]) -> int:
    return sum(len(rounds) for rounds in excess.values())


def _flipped(matches: Round, pair: Pairing) -> Round:
    return [(m[1], m[0]) if m == pair else m for m in matches]


def _improve(first_half: list[Round], order: Sequence[int], rng: WorldRng) -> list[Round]:
    """Flip fixtures and their return fixtures in over-long streaks; keep non-worsening flips."""
    half = len(first_half)
    excess = _streak_excess(_full(first_half, order))
    for _ in range(FLIP_BUDGET):
        if not excess:
            return first_half
        club = rng.choice(sorted(excess))
        picked = rng.choice(excess[club])
        number = picked if picked < half else order[picked - half]
        pair = rng.choice([m for m in first_half[number] if club in m])
        before = first_half[number]
        first_half[number] = _flipped(before, pair)
        candidate = _streak_excess(_full(first_half, order))
        if _cost(candidate) <= _cost(excess):
            excess = candidate
        else:
            first_half[number] = before
    return first_half


def _attempt(
    rounds: list[list[tuple[ClubId, ClubId]]], rng: WorldRng, derbies: Collection[frozenset[ClubId]]
) -> list[Round]:
    order = rng.shuffled(rounds)
    order.sort(
        key=lambda pairs: any(frozenset(pair) in derbies for pair in pairs)
    )  # derby rounds late
    return_order = list(range(len(order)))
    if rng.bernoulli(0.5):  # the return half usually repeats the order; sometimes it is reshuffled
        rng.shuffle(return_order)
        return_order.sort(key=lambda index: any(frozenset(p) in derbies for p in order[index]))
    first_half = _improve(_berger(order), return_order, rng)
    return _full(first_half, return_order)


def build_rounds(
    clubs: Sequence[ClubId], rng: WorldRng, derbies: Collection[frozenset[ClubId]] = ()
) -> list[Round]:
    """Rounds of (home, away) pairings; retries random orders until the schedule validates."""
    if len(clubs) < 2:  # noqa: PLR2004 - a league needs two clubs
        msg = "a schedule needs at least two clubs"
        raise ScheduleError(msg)
    rounds = circle_rounds(clubs)
    for attempt in range(MAX_ATTEMPTS):
        candidate = _attempt(rounds, rng.fork(f"attempt:{attempt}"), derbies)
        fixtures = _as_fixtures(candidate)
        if not check_schedule(fixtures, clubs, derbies):
            return candidate
    msg = f"no valid schedule for {len(clubs)} clubs after {MAX_ATTEMPTS} attempts"
    raise ScheduleError(msg)


def _as_fixtures(rounds: Sequence[Round]) -> list[Fixture]:
    """Throw-away fixtures (numbered by matchday) used only to validate a candidate."""
    fixtures = []
    for matchday, matches in enumerate(rounds, start=1):
        for index, (home, away) in enumerate(matches):
            fixtures.append(
                Fixture(
                    id=FixtureId(f"fix_t{matchday:03d}{index:02d}"[:12]),
                    competition_id=CompetitionId("cmp_00001"),
                    season_id=SeasonId("ssn_00001"),
                    matchday=matchday,
                    date=dt.date(2000, 1, 1),
                    home_club_id=home,
                    away_club_id=away,
                    stadium_id=StadiumId("std_00001"),
                )
            )
    return fixtures


def stadium_id_for(club_id: ClubId) -> StadiumId:
    """A club's ground id, derived from the club id (``clb_00004`` -> ``std_00004``)."""
    return StadiumId("std_" + club_id.removeprefix("clb_"))


def schedule_fixtures(
    rounds: Sequence[Round],
    season: tuple[CompetitionId, SeasonId],
    dates: Sequence[dt.date],
    derbies: Collection[frozenset[ClubId]] = (),
) -> list[Fixture]:
    """Dated fixtures; ``dates`` has one date per matchday.

    Ids are derived from the season, matchday and pairing, so the same schedule always gets the
    same ids; fixtures between derby rivals are flagged.
    """
    competition_id, season_id = season
    fixtures = []
    for matchday, matches in enumerate(rounds, start=1):
        for home, away in matches:
            fixtures.append(
                Fixture(
                    id=FixtureId(derive_id("fixture", season_id, str(matchday), home, away)),
                    competition_id=competition_id,
                    season_id=season_id,
                    matchday=matchday,
                    date=dates[matchday - 1],
                    home_club_id=home,
                    away_club_id=away,
                    stadium_id=stadium_id_for(home),
                    is_derby=frozenset((home, away)) in derbies,
                )
            )
    return fixtures
