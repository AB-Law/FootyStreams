"""Read a side's people from the repositories into the plain inputs the pure code takes."""

from __future__ import annotations

from footystreams.domain.mood import StateModifier
from footystreams.domain.types import ClubId
from footystreams.league.setup import TeamInputs
from footystreams.persistence.ports import NotFoundError, Repositories

PLAYER_OWNER = "player"
ACTIVE = "active"


class MissingManagerError(NotFoundError):
    """A club has no manager, so it cannot field a team."""

    def __init__(self, club_id: str) -> None:
        """Name the club."""
        super().__init__("manager", club_id)


def load_team(repositories: Repositories, club_id: ClubId) -> TeamInputs:
    """The club, its manager, staff, active squad and the modifiers of every squad player."""
    club = repositories.clubs.require(club_id)
    managers = repositories.managers.find({"club_id": club_id})
    if not managers:
        raise MissingManagerError(club_id)
    squad = repositories.players.find({"club_id": club_id, "status": ACTIVE})
    modifiers: dict[str, list[StateModifier]] = {}
    for player in squad:
        found = repositories.modifiers.find({"owner_kind": PLAYER_OWNER, "owner_id": player.id})
        if found:
            modifiers[player.id] = found
    return TeamInputs(
        club=club,
        manager=managers[0],
        staff=repositories.staff.find({"club_id": club_id}),
        squad=squad,
        modifiers=modifiers,
    )
