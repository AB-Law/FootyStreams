"""Pack a BroadcastBrief from a World and a match setup/summary (pure; no I/O)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.club import Club, Rivalry
from footystreams.domain.manager import Manager, ManagerStint
from footystreams.domain.match import MatchSetup, TeamSheet
from footystreams.domain.media import MediaPersonality, MediaRole
from footystreams.domain.mood import ModifierVisibility, WorldEvent
from footystreams.domain.player import CareerStint, Player
from footystreams.domain.relationship import Relationship
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import ClubId, EntityKind, PlayerId
from footystreams.domain.world import WiderClub, World
from footystreams.events.summary import MatchSummary
from footystreams.extensions.brief import (
    BroadcastBrief,
    CareerLine,
    ClubBrief,
    CrewMember,
    ManagerBrief,
    NewsItem,
    PersonBrief,
    RelationshipBrief,
    ScoreBrief,
)

TOP_PLAYERS_PER_SIDE = 5
STUDIO_ROLES = frozenset(
    {MediaRole.PRESENTER, MediaRole.PUNDIT, MediaRole.REPORTER, MediaRole.CO_COMMENTATOR}
)


def pack_broadcast_brief(
    world: World,
    setup: MatchSetup,
    summary: MatchSummary | None = None,
    news: Sequence[WorldEvent] = (),
) -> BroadcastBrief:
    """Assemble speakable facts for the home/away match; invents nothing."""
    wider = {club.id: club for club in world.wider_clubs}
    players = {str(player.id): player for player in world.players}
    managers = {str(manager.id): manager for manager in world.managers}
    clubs = {club.id: club for club in world.clubs}
    names = _name_index(world)
    home_club = clubs[setup.home.club.id]
    away_club = clubs[setup.away.club.id]
    featured = _featured_players(setup, summary, players, wider)
    return BroadcastBrief(
        match_id=setup.match_id,
        home=_club_brief(home_club),
        away=_club_brief(away_club),
        home_manager=_manager_brief(setup.home, "home", managers, wider),
        away_manager=_manager_brief(setup.away, "away", managers, wider),
        players=featured,
        relationships=_relationships(world.relationships, featured, names),
        news=_news_items(news),
        score=_score(summary, players),
        hooks=tuple(hook.kind for hook in summary.hooks) if summary else (),
        key_moments=_key_moments(summary),
        crew=_crew(world.media),
        team_stats_note=_stats_note(summary),
    )


def _club_brief(club: Club) -> ClubBrief:
    rivalry = _primary_rivalry(club.rivalries)
    return ClubBrief(
        id=str(club.id),
        name=club.name,
        nickname=club.nickname,
        short_code=club.short_code,
        founded_year=club.founded_year,
        city=club.location.city,
        rivalry_label=rivalry.label if rivalry else "",
        rivalry_origin=rivalry.origin if rivalry else "",
    )


def _primary_rivalry(rivalries: tuple[Rivalry, ...]) -> Rivalry | None:
    if not rivalries:
        return None
    return max(rivalries, key=lambda row: row.intensity)


def _manager_brief(
    sheet: TeamSheet,
    side: str,
    managers: Mapping[str, Manager],
    wider: Mapping[ClubId, WiderClub],
) -> ManagerBrief | None:
    manager = managers.get(str(sheet.manager.id))
    if manager is None:
        return None
    return ManagerBrief(
        id=str(manager.id),
        known_as=manager.known_as,
        side=side,  # type: ignore[arg-type]
        style=manager.style.value,
        press_tone=manager.press_style.tone.value,
        career=tuple(manager_career_line(stint, wider) for stint in manager.career_history),
    )


def manager_career_line(stint: ManagerStint, wider: Mapping[ClubId, WiderClub]) -> CareerLine:
    """One managerial spell as a speakable line, with the club named if it is a wider club."""
    named = wider.get(stint.club_id)
    detail = f"{stint.played} played, {stint.won}W {stint.drawn}D {stint.lost}L"
    end = stint.to_date.year if stint.to_date is not None else stint.from_date.year
    return CareerLine(
        club_name=named.name if named else None,
        from_year=stint.from_date.year,
        to_year=end,
        detail=detail,
    )


def player_career_line(stint: CareerStint, wider: Mapping[ClubId, WiderClub]) -> CareerLine:
    """One playing spell as a speakable line, with the club named if it is a wider club."""
    named = wider.get(stint.club_id)
    detail = f"{stint.apps} apps, {stint.goals} goals"
    end = stint.to_date.year if stint.to_date is not None else stint.from_date.year
    return CareerLine(
        club_name=named.name if named else None,
        from_year=stint.from_date.year,
        to_year=end,
        detail=detail,
    )


def _featured_players(
    setup: MatchSetup,
    summary: MatchSummary | None,
    players: Mapping[str, Player],
    wider: Mapping[ClubId, WiderClub],
) -> tuple[PersonBrief, ...]:
    rating_by_id = {row.player_id: row.rating for row in (summary.ratings if summary else ())}
    rows: list[PersonBrief] = []
    for side, sheet in (("home", setup.home), ("away", setup.away)):
        for snapshot, role in _rank_side(sheet, rating_by_id):
            player = players.get(str(snapshot.id))
            rows.append(_person_brief(snapshot, role, side, player, wider))
    return tuple(rows)


def _rank_side(
    sheet: TeamSheet, rating_by_id: Mapping[PlayerId, float]
) -> list[tuple[PlayerSnapshot, str]]:
    starters: list[tuple[PlayerSnapshot, str]] = []
    for slot in sheet.lineup:
        snapshot = sheet.squad.get(slot.player_id)
        if snapshot is not None:
            starters.append((snapshot, slot.role))
    starters.sort(key=lambda pair: (-rating_by_id.get(pair[0].id, 0.0), pair[0].known_as))
    return starters[:TOP_PLAYERS_PER_SIDE]


def _person_brief(
    snapshot: PlayerSnapshot,
    role: str,
    side: str,
    player: Player | None,
    wider: Mapping[ClubId, WiderClub],
) -> PersonBrief:
    career = (
        tuple(player_career_line(stint, wider) for stint in player.career_history)
        if player is not None
        else ()
    )
    keys = tuple(snapshot.public_storylines) or tuple(snapshot.mood.public_storyline_keys)
    return PersonBrief(
        id=str(snapshot.id),
        known_as=snapshot.known_as,
        role=role,
        side=side,  # type: ignore[arg-type]
        age=snapshot.age,
        career=career,
        storyline_keys=keys,
    )


def _name_index(world: World) -> dict[tuple[str, str], str]:
    names: dict[tuple[str, str], str] = {}
    for player in world.players:
        names[(EntityKind.PLAYER.value, str(player.id))] = player.known_as
    for manager in world.managers:
        names[(EntityKind.MANAGER.value, str(manager.id))] = manager.known_as
    for club in world.clubs:
        names[(EntityKind.CLUB.value, str(club.id))] = club.name
    return names


def _relationships(
    rows: Sequence[Relationship],
    featured: Sequence[PersonBrief],
    names: Mapping[tuple[str, str], str],
) -> tuple[RelationshipBrief, ...]:
    ids = {person.id for person in featured}
    found: list[RelationshipBrief] = []
    for row in rows:
        if not row.public:
            continue
        if str(row.a.id) not in ids and str(row.b.id) not in ids:
            continue
        a_name = names.get((row.a.kind.value, str(row.a.id)), str(row.a.id))
        b_name = names.get((row.b.kind.value, str(row.b.id)), str(row.b.id))
        found.append(
            RelationshipBrief(kind=row.kind, a_name=a_name, b_name=b_name, strength=row.strength)
        )
    return tuple(found[:12])


def _news_items(news: Sequence[WorldEvent]) -> tuple[NewsItem, ...]:
    items: list[NewsItem] = []
    for event in news:
        if event.visibility != ModifierVisibility.PUBLIC:
            continue
        facts = ", ".join(f"{key}={value}" for key, value in sorted(event.facts.items()))
        items.append(
            NewsItem(kind=event.kind, date=event.date.isoformat(), summary=facts or event.kind)
        )
    return tuple(items[:20])


def _score(summary: MatchSummary | None, players: Mapping[str, Player]) -> ScoreBrief | None:
    if summary is None:
        return None
    potm = players.get(str(summary.player_of_the_match)) if summary.player_of_the_match else None
    return ScoreBrief(
        home=summary.score_home,
        away=summary.score_away,
        ht_home=summary.ht_home,
        ht_away=summary.ht_away,
        potm_name=potm.known_as if potm else None,
    )


def _key_moments(summary: MatchSummary | None) -> tuple[str, ...]:
    if summary is None:
        return ()
    return tuple(f"{moment.kind}@{moment.t}s" for moment in summary.key_moments[:8])


def _crew(media: Sequence[MediaPersonality]) -> tuple[CrewMember, ...]:
    studio = [person for person in media if person.role in STUDIO_ROLES]
    chosen = studio or list(media)[:3]
    return tuple(
        CrewMember(
            id=str(person.id),
            known_as=person.known_as,
            role=person.role.value,
            catchphrases=person.catchphrases,
            expertise_tags=person.expertise_tags,
        )
        for person in chosen[:4]
    )


def _stats_note(summary: MatchSummary | None) -> str:
    if summary is None:
        return ""
    home = summary.team_stats_home
    away = summary.team_stats_away
    return (
        f"shots {home.shots}-{away.shots}, xG {home.xg:.2f}-{away.xg:.2f}, "
        f"possession {home.possession:.0%}-{away.possession:.0%}"
    )
