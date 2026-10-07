"""``LeagueTables``: every static table the league reads, loaded once by a composition root."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import FormationCatalog, InjuryCatalog
from footystreams.league.climate import ClimateCatalog
from footystreams.league.config import LeagueConfig
from footystreams.league.development_config import DevelopmentConfig
from footystreams.league.mood_config import MoodConfig
from footystreams.league.post_match import PostMatchTables
from footystreams.league.setup import SetupTables
from footystreams.league.transfer_config import TransferConfig


@dataclass(frozen=True, slots=True)
class LeagueTables:
    """Roles, formations, injuries, climate, league and mood configuration."""

    roles: RoleCatalog
    formations: FormationCatalog
    injuries: InjuryCatalog
    climate: ClimateCatalog
    config: LeagueConfig
    mood: MoodConfig
    development: DevelopmentConfig
    transfer: TransferConfig

    @property
    def setup(self) -> SetupTables:
        """The slice of tables ``build_match_setup`` reads."""
        return SetupTables(
            roles=self.roles,
            formations=self.formations,
            mood=self.mood,
            recovery=self.config.recovery,
        )

    @property
    def post_match(self) -> PostMatchTables:
        """The slice of tables ``derive_world_delta`` reads."""
        return PostMatchTables(
            injuries=self.injuries,
            recovery=self.config.recovery,
            finance=self.config.finance,
            mood=self.mood,
        )
