"""The newsroom: a world indexed for the show, and who sits at the desk."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.manager import Manager
from footystreams.domain.media import MediaPersonality, MediaRole
from footystreams.domain.player import Player
from footystreams.domain.types import ClubId
from footystreams.domain.world import WiderClub, World
from footystreams.extensions.show.models import CastMember
from footystreams.extensions.show.textutil import fold

DESK_SIZE = 3
MIN_NAME_LENGTH = 4
_JOKER_ROLES = (MediaRole.PRESENTER, MediaRole.PUNDIT)


def _sorted_by_humor(
    people: Sequence[MediaPersonality], *, funniest: bool
) -> list[MediaPersonality]:
    sign = -1 if funniest else 1
    return sorted(people, key=lambda person: (sign * person.personality.humor, str(person.id)))


def _member(person: MediaPersonality, city: str) -> CastMember:
    return CastMember(
        id=str(person.id),
        name=person.known_as,
        role=person.role.value,
        humor=person.personality.humor,
        interview_style=person.personality.interview_style,
        expertise=person.expertise_tags,
        catchphrases=person.catchphrases,
        birthplace=city,
    )


def choose_desk(media: Sequence[MediaPersonality]) -> tuple[MediaPersonality, ...]:
    """Three hosts to play off each other: funniest presenter and pundit, then a straight man.

    The straight man is the least funny of the rest of the studio crew, so there is always someone
    to be deadpan about the jokes. Falls back to whoever is available in a small world.
    """
    desk: list[MediaPersonality] = []
    for role in _JOKER_ROLES:
        pool = _sorted_by_humor([person for person in media if person.role is role], funniest=True)
        if pool:
            desk.append(pool[0])
    rest = [person for person in media if person not in desk and person.role not in _JOKER_ROLES]
    desk += _sorted_by_humor(rest or [p for p in media if p not in desk], funniest=False)[
        : DESK_SIZE - len(desk)
    ]
    return tuple(desk[:DESK_SIZE])


class Newsroom:
    """A world with the lookups the show needs, built once."""

    def __init__(self, world: World) -> None:
        """Index clubs, people and career clubs by id."""
        self.world = world
        self.clubs: dict[str, Club] = {str(club.id): club for club in world.clubs}
        self.managers: dict[str, Manager] = {str(manager.id): manager for manager in world.managers}
        self.players: dict[str, Player] = {str(player.id): player for player in world.players}
        self.wider: dict[ClubId, WiderClub] = {club.id: club for club in world.wider_clubs}
        self.cities = {str(city.id): city.name for city in world.cities}
        self.club_of_player = {
            str(entry.player_id): str(entry.club_id) for entry in world.squad_entries
        }
        self.club_names = {club_id: club.name for club_id, club in self.clubs.items()}

    def manager_of(self, club_id: str) -> Manager | None:
        """The manager in charge of the club, if it has one."""
        manager_id = self.clubs[club_id].manager_id
        return self.managers.get(str(manager_id)) if manager_id else None

    def desk(self) -> tuple[CastMember, ...]:
        """The three hosts, with their hometowns resolved."""
        return tuple(
            _member(person, self.cities.get(person.birthplace.city, person.birthplace.city))
            for person in choose_desk(self.world.media)
        )

    def directory(self) -> list[dict[str, str]]:
        """Everyone a guest could be, for the control room: managers first, then players."""
        people = [
            (m.known_as, "manager", self._club_of_manager(str(m.id)))
            for m in self.managers.values()
        ]
        players = self.players.items()
        people += [
            (p.known_as, "player", self.club_names.get(self.club_of_player.get(pid, ""), ""))
            for pid, p in players
        ]
        ids = [*self.managers, *self.players]
        return [
            {"id": ids[index], "name": name, "role": role, "club": club}
            for index, (name, role, club) in enumerate(people)
        ]

    def _club_of_manager(self, manager_id: str) -> str:
        return next((c.name for c in self.clubs.values() if str(c.manager_id) == manager_id), "")

    def vocabulary(self) -> tuple[str, ...]:
        """Every proper name in the world, so a host naming one that is not in play is caught."""
        names = {club.name for club in self.clubs.values()} | {
            club.short_name for club in self.clubs.values()
        }
        names |= {club.stadium.name for club in self.clubs.values()}
        names |= {club.name for club in self.wider.values()}
        names |= {person.known_as for person in (*self.players.values(), *self.managers.values())}
        names |= {person.known_as for person in self.world.media}
        return tuple(sorted(name for name in names if len(fold(name)) >= MIN_NAME_LENGTH))
