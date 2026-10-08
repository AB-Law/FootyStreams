"""Load the state a rollover needs from the repositories."""

from __future__ import annotations

from footystreams.domain.competition import Season
from footystreams.league.awards import season_totals
from footystreams.league.matchday import current_table
from footystreams.league.rollover_state import KEY_REFERENCE_ABILITY, RolloverData
from footystreams.persistence.ports import Repositories

ACTIVE = "active"
FREE_AGENT = "free_agent"
RETIRED = "retired"


def load_rollover_data(repositories: Repositories, season: Season) -> RolloverData:
    """The competition, clubs, people, table and season totals of a season that has ended."""
    competition = repositories.competitions.require(season.competition_id)
    clubs = {club_id: repositories.clubs.require(club_id) for club_id in competition.club_ids}
    matches = repositories.matches.find({"season_id": season.id})
    summaries = [
        stored.summary
        for match in matches
        for stored in repositories.summaries.find({"match_id": match.id})
    ]
    return RolloverData(
        season=season,
        competition=competition,
        clubs=clubs,
        players=[
            *repositories.players.find({"status": ACTIVE}),
            *repositories.players.find({"status": FREE_AGENT}),
        ],
        staff={cid: repositories.staff.find({"club_id": cid}) for cid in clubs},
        entries={cid: repositories.squad_entries.find({"club_id": cid}) for cid in clubs},
        table=current_table(repositories, season.id, competition.club_ids),
        totals=season_totals(summaries),
        retired_names=repositories.players.find({"status": RETIRED}),
        reference_ability=_reference(repositories),
    )


def _reference(repositories: Repositories) -> float | None:
    entry = repositories.meta.get(KEY_REFERENCE_ABILITY)
    return float(entry.value) if entry is not None else None
