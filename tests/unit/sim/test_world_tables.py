from __future__ import annotations

from footystreams.seed.static.simple_tables import load_formations
from footystreams.sim.tables import tables_from_catalog


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
