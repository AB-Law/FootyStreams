"""The rundown: what the show does next, decided from the bible alone so a restart picks up exactly.

Each fixture is six stretches of airtime: a preview, a filler, the recap of that match, a post-match
interview with a guest, then the table (after a matchday) or another filler, and a break. The
filler rotates through club history, manager and player stories and plenty of banter, always taking
whoever has been off air longest. A guest someone has asked for takes the next interview slot's
place without moving the rundown.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.world import World
from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.models import SegmentKind
from footystreams.extensions.show.schedule import Pairing, season_fixtures

FILLERS = (
    SegmentKind.CLUB_HISTORY,
    SegmentKind.BANTER,
    SegmentKind.MANAGER_STORY,
    SegmentKind.BANTER,
    SegmentKind.PLAYER_STORY,
    SegmentKind.BANTER,
)
STEP_PREVIEW, STEP_FILLER, STEP_RECAP, STEP_INTERVIEW, STEP_AFTER, STEP_BREAK = range(6)
STEPS = 6
PREFIXES: Mapping[SegmentKind, str] = {
    SegmentKind.CLUB_HISTORY: "club",
    SegmentKind.MANAGER_STORY: "manager",
    SegmentKind.PLAYER_STORY: "player",
}


@dataclass(frozen=True, slots=True)
class Roster:
    """The ids the rundown draws its fixtures and subjects from."""

    fixtures: tuple[Pairing, ...]
    clubs: tuple[str, ...]
    managers: tuple[str, ...]
    players: tuple[str, ...]
    manager_of: Mapping[str, str]

    @property
    def per_matchday(self) -> int:
        """Fixtures in one matchday."""
        return max(len(self.clubs) // 2, 1)

    @classmethod
    def from_world(cls, world: World) -> Roster:
        """The fixtures and subjects of a world: managers, and players with a career to tell."""
        clubs = tuple(sorted(str(club.id) for club in world.clubs))
        return cls(
            fixtures=season_fixtures(clubs),
            clubs=clubs,
            managers=tuple(sorted(str(manager.id) for manager in world.managers)),
            players=tuple(sorted(str(p.id) for p in world.players if p.career_history)),
            manager_of={str(c.id): str(c.manager_id) for c in world.clubs if c.manager_id},
        )


@dataclass(frozen=True, slots=True)
class Plan:
    """The next stretch of the show.

    ``off_rundown`` marks a segment that was asked for (a guest, breaking news): it takes airtime
    without moving the rundown on.
    """

    number: int
    kind: SegmentKind
    season: int
    pairing: Pairing | None = None
    subject: str = ""
    off_rundown: bool = False

    def fixture(self) -> Pairing:
        """The fixture of a preview or recap."""
        if self.pairing is None:
            msg = f"segment {self.number} ({self.kind.value}) has no fixture"
            raise ValueError(msg)
        return self.pairing


def kind_for(bible: ShowBible) -> SegmentKind:
    """What comes next in the six-part cycle."""
    kinds = {
        STEP_PREVIEW: SegmentKind.PREVIEW,
        STEP_RECAP: SegmentKind.RECAP,
        STEP_INTERVIEW: SegmentKind.INTERVIEW,
        STEP_BREAK: SegmentKind.BREAK,
    }
    if bible.step in kinds:
        return kinds[bible.step]
    if bible.step == STEP_AFTER and bible.table_due:
        return SegmentKind.TABLE_TALK
    return FILLERS[bible.filler_index % len(FILLERS)]


def _stalest(candidates: Sequence[str], featured: Mapping[str, int], prefix: str) -> str:
    return min(candidates, key=lambda item: (featured.get(f"{prefix}:{item}", 0), item))


def _post_match_guest(bible: ShowBible, roster: Roster) -> str:
    """Who sits down after a match: its player of the match, or on alternate ones a manager."""
    last = bible.results[-1] if bible.results else None
    if last is None:
        return _stalest(roster.managers, bible.featured, "guest") if roster.managers else ""
    manager = roster.manager_of.get(last.home_id, "")
    if last.potm_id and (bible.fixture_index % 2 == 1 or not manager):
        return last.potm_id
    return manager or last.potm_id


def _subject(kind: SegmentKind, bible: ShowBible, roster: Roster) -> str:
    if kind is SegmentKind.INTERVIEW:
        return _post_match_guest(bible, roster)
    pools = {
        SegmentKind.CLUB_HISTORY: roster.clubs,
        SegmentKind.MANAGER_STORY: roster.managers,
        SegmentKind.PLAYER_STORY: roster.players,
    }
    pool = pools.get(kind)
    if not pool:
        return ""
    return _stalest(pool, bible.featured, PREFIXES[kind])


def next_plan(bible: ShowBible, roster: Roster) -> Plan:
    """What the show airs next, given what it has already aired."""
    number = bible.segment_count + 1
    if bible.requests:
        guest = bible.requests[0].person_id
        return Plan(number, SegmentKind.INTERVIEW, bible.season, subject=guest, off_rundown=True)
    kind = kind_for(bible)
    pairing = (
        roster.fixtures[bible.fixture_index]
        if kind in {SegmentKind.PREVIEW, SegmentKind.RECAP}
        else None
    )
    return Plan(number, kind, bible.season, pairing, _subject(kind, bible, roster))


def _features(bible: ShowBible, plan: Plan) -> dict[str, int]:
    """Who has now been on the desk, by segment number, for the stalest-first picks."""
    prefix = PREFIXES.get(plan.kind)
    if plan.subject and prefix:
        return {**bible.featured, f"{prefix}:{plan.subject}": plan.number}
    if plan.subject and plan.kind is SegmentKind.INTERVIEW:
        return {**bible.featured, f"guest:{plan.subject}": plan.number}
    return dict(bible.featured)


def advance(bible: ShowBible, plan: Plan, roster: Roster) -> ShowBible:
    """The bible after ``plan`` has aired: the cycle moves on, the subject is marked as featured."""
    update: dict[str, object] = {
        "segment_count": plan.number,
        "failures": 0,
        "featured": _features(bible, plan),
    }
    if plan.off_rundown:
        update["requests"] = (
            bible.requests[1:] if plan.kind is SegmentKind.INTERVIEW else bible.requests
        )
        return bible.model_copy(update=update)
    if plan.kind in FILLERS:
        update["filler_index"] = bible.filler_index + 1
    update["step"] = (bible.step + 1) % STEPS
    if plan.kind is SegmentKind.RECAP:
        index = bible.fixture_index + 1
        update["fixture_index"] = index
        update["table_due"] = index % roster.per_matchday == 0
    if bible.step == STEP_AFTER:
        update["table_due"] = False
    if bible.step == STEP_BREAK and bible.fixture_index >= len(roster.fixtures):
        update["season"] = bible.season + 1
        update["fixture_index"] = 0
    return bible.model_copy(update=update)
