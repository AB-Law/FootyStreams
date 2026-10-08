import pytest

from footystreams.domain.types import FormationId, Position
from footystreams.sim.tables import default_tables
from tests.factories.sim_teams import make_demo_setup, make_demo_sheet


@pytest.mark.parametrize("formation", sorted(default_tables().formations))
def test_make_demo_sheet__every_builtin_formation_gives_a_valid_sheet(formation: str) -> None:
    sheet = make_demo_sheet("home", formation=formation)
    table = default_tables().formations[FormationId(formation)]
    assert len(sheet.lineup) == 11
    for slot in sheet.lineup:
        snapshot = sheet.squad[slot.player_id]
        assert snapshot.position_competence[table.slots[slot.slot].position] == 90


def test_make_demo_sheet__keeper_is_a_goalkeeping_specialist_and_forward_a_finisher() -> None:
    sheet = make_demo_sheet("home", strength=60)
    keeper = sheet.squad[sheet.lineup[0].player_id]
    striker = sheet.squad[sheet.lineup[10].player_id]
    assert keeper.goalkeeping.shot_stopping > 60
    assert striker.technical.finishing > keeper.technical.finishing
    assert keeper.position_competence[Position.GK] == 90


def test_make_demo_sheet__bench_has_a_goalkeeper() -> None:
    sheet = make_demo_sheet("away")
    assert any(
        sheet.squad[player_id].position_competence[Position.GK] == 90 for player_id in sheet.bench
    )


def test_make_demo_setup__stronger_side_has_better_attributes() -> None:
    setup = make_demo_setup(home_strength=80, away_strength=50)
    home = setup.home.squad[setup.home.lineup[8].player_id]
    away = setup.away.squad[setup.away.lineup[8].player_id]
    assert home.technical.finishing > away.technical.finishing
    assert setup.home.club.short_code == "KES"
    assert setup.away.club.short_code == "HAR"
