"""``WorldReader`` over any repositories (one implementation serves every backend)."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.club import Club
from footystreams.domain.fixture import Fixture
from footystreams.domain.manager import Manager
from footystreams.domain.player import Player
from footystreams.domain.referee import Referee
from footystreams.domain.staff import StaffMember
from footystreams.persistence.ports import Repositories
from footystreams.persistence.world_store import KEY_CURRENT_DATE, read_meta


class RepositoryWorldReader:
    """Read-only world access built from the repository ports."""

    def __init__(self, repositories: Repositories) -> None:
        """Wrap the repositories of a database or an open unit of work."""
        self._repositories = repositories

    def current_date(self) -> dt.date:
        """The in-world date."""
        return dt.date.fromisoformat(read_meta(self._repositories, KEY_CURRENT_DATE))

    def club(self, club_id: str) -> Club:
        """A club; raises NotFoundError."""
        return self._repositories.clubs.require(club_id)

    def clubs(self) -> list[Club]:
        """All clubs ordered by id."""
        return self._repositories.clubs.all()

    def player(self, player_id: str) -> Player:
        """A player; raises NotFoundError."""
        return self._repositories.players.require(player_id)

    def squad(self, club_id: str) -> list[Player]:
        """Players under contract with the club, ordered by id."""
        return self._repositories.players.find({"club_id": club_id})

    def free_agents(self) -> list[Player]:
        """Players without a club, ordered by id."""
        return self._repositories.players.find({"club_id": None, "status": "free_agent"})

    def manager_of(self, club_id: str) -> Manager | None:
        """The club's manager, if any."""
        managers = self._repositories.managers.find({"club_id": club_id})
        return managers[0] if managers else None

    def staff_of(self, club_id: str) -> list[StaffMember]:
        """The club's staff, ordered by id."""
        return self._repositories.staff.find({"club_id": club_id})

    def referees(self) -> list[Referee]:
        """All referees ordered by id."""
        return self._repositories.referees.all()

    def fixtures(self, season_id: str, matchday: int | None = None) -> list[Fixture]:
        """Fixtures of a season (optionally one matchday), ordered by id."""
        criteria: dict[str, str | int] = {"season_id": season_id}
        if matchday is not None:
            criteria["matchday"] = matchday
        return self._repositories.fixtures.find(criteria)

    def ledger_balance(self, club_id: str) -> int:
        """Sum of the club's ledger entries."""
        return self._repositories.ledger.total("amount", {"club_id": club_id})
