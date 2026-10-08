"""A delta that creates a club and a player under contract to it must apply on SQLite.

The outside-world club is created lazily in the same delta as the first player who signs with
it; players were written first, so the foreign key from the contract to the club failed.
"""

from __future__ import annotations

from footystreams.domain.ids import derive_id
from footystreams.domain.types import ClubId
from footystreams.league.delta import WorldDelta, apply_delta
from tests.factories.league_run import make_factory
from tests.factories.world import make_world

NEW_CLUB = ClubId("clb_zz001")


def test_apply_delta__new_club_and_its_new_player__applies_on_sql() -> None:
    world = make_world(2, 4)
    factory = make_factory(world, "sql")
    template = next(p for p in world.players if p.contract is not None)
    assert template.contract is not None
    signed = template.model_copy(
        update={
            "id": derive_id("player", "regression-0101"),
            "contract": template.contract.model_copy(update={"club_id": NEW_CLUB}),
        }
    )
    club = world.clubs[0].model_copy(
        update={"id": NEW_CLUB, "short_code": "ZZZ", "name": "Regression FC"}
    )
    with factory() as uow:
        apply_delta(uow, WorldDelta(players=(signed,), clubs=(club,)))
        uow.commit()
    with factory() as uow:
        stored = uow.players.get(signed.id)
    assert stored is not None
    assert stored.contract is not None
