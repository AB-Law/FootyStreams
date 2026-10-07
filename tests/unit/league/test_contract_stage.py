from __future__ import annotations

import datetime as dt

from footystreams.domain.player import PlayerStatus
from footystreams.domain.rng import WorldRng
from footystreams.league.delta import apply_delta
from footystreams.league.stages import ContractExpiryStage
from tests.factories.league_db import make_league_db
from tests.factories.league_inputs import make_league_tables


def test_contract_expiry_stage__releases_expired_players_only_the_day_after_the_end_day() -> None:
    factory = make_league_db()
    stage = ContractExpiryStage(make_league_tables())
    with factory() as uow:
        victim = next(p for p in uow.players.find({"status": "active"}) if p.contract)
        assert victim.contract is not None
        key = f"{victim.contract.club_id}:{victim.id}"
        ended = victim.model_copy(
            update={"contract": victim.contract.model_copy(update={"end": dt.date(2032, 6, 30)})}
        )
        uow.players.save(ended)
        assert stage.run(uow, dt.date(2032, 6, 30), WorldRng(1)).is_empty()
        delta = stage.run(uow, dt.date(2032, 7, 1), WorldRng(1))
        apply_delta(uow, delta)
        freed = uow.players.require(victim.id)
        gone = uow.squad_entries.get(key)
    assert freed.status is PlayerStatus.FREE_AGENT
    assert freed.contract is None
    assert gone is None
