from __future__ import annotations

import pytest

from footystreams.seed.static.simple_tables import load_formations
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import tables_from_catalog
from tests.factories.sim_teams import make_demo_setup


def test_tables_from_catalog__every_world_formation_is_playable() -> None:
    catalog = load_formations()

    tables = tables_from_catalog(catalog)

    assert sorted(tables.formations) == sorted(catalog.formations)


def test_tables_from_catalog__keeps_each_slot_position_and_coordinates() -> None:
    catalog = load_formations()

    tables = tables_from_catalog(catalog)

    for formation_id, formation in catalog.formations.items():
        converted = tables.formations[formation_id]
        assert [(s.position, s.x, s.y) for s in converted.slots] == [
            (s.position, s.x, s.y) for s in formation.slots
        ]


def test_tables_from_catalog__has_no_role_catalogue() -> None:
    assert tables_from_catalog(load_formations()).roles is None


@pytest.mark.parametrize("formation_id", sorted(load_formations().formations))
def test_tables_from_catalog__a_match_can_be_played_in_every_world_formation(
    formation_id: str,
) -> None:
    setup = make_demo_setup(home_formation=formation_id, away_formation=formation_id)

    result = run_match(setup, 7, SimConfig(), tables_from_catalog(load_formations()))

    assert result.log_digest
