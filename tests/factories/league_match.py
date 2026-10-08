"""Setups with a tunable squad level and mood, for the league's simulator tests."""

from __future__ import annotations

from footystreams.domain.match import MatchSetup, TeamSheet
from footystreams.domain.mood import ResolvedMood
from footystreams.domain.types import PlayerId
from tests.factories.match import make_player_snapshot, make_setup, make_team_sheet
from tests.factories.player import make_mental, make_physical, make_technical


def make_leveled_sheet(level: int, side: str, club_id: str) -> TeamSheet:
    """A valid sheet whose squad has every outfield attribute at ``level``."""
    sheet = make_team_sheet(club_id=club_id, side=side)
    squad = {
        pid: make_player_snapshot(
            id=pid,
            known_as=snapshot.known_as,
            position_competence=snapshot.position_competence,
            technical=make_technical(**dict.fromkeys(type(snapshot.technical).model_fields, level)),
            mental=make_mental(**dict.fromkeys(type(snapshot.mental).model_fields, level)),
            physical=make_physical(**dict.fromkeys(type(snapshot.physical).model_fields, level)),
        )
        for pid, snapshot in sheet.squad.items()
    }
    return sheet.model_copy(update={"squad": squad})


def make_leveled_setup(home_level: int = 60, away_level: int = 60) -> MatchSetup:
    """A setup between two flat squads of the given levels."""
    return make_setup(
        home=make_leveled_sheet(home_level, "home", "clb_home01"),
        away=make_leveled_sheet(away_level, "away", "clb_away01"),
    )


def with_mood(setup: MatchSetup, player_id: PlayerId, multiplier: float) -> MatchSetup:
    """The setup with one home player's three mood multipliers set to ``multiplier``."""
    mood = ResolvedMood(mental_mult=multiplier, technical_mult=multiplier, physical_mult=multiplier)
    snapshot = setup.home.squad[player_id].model_copy(update={"mood": mood})
    home = setup.home.model_copy(update={"squad": {**setup.home.squad, player_id: snapshot}})
    return setup.model_copy(update={"home": home})
