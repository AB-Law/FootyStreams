"""Academy players created at the rollover must be as old as the request says on that day.

The seed adapter once created players relative to the date the world was generated, so intake
from the second season on was older than asked for and the academy ran dry.
"""

from __future__ import annotations

import datetime as dt

from footystreams.league.youth import contract_end
from tests.factories.league_config import make_development_config
from tests.factories.league_run import cached_rolled_over

ROLLOVER_DAY = dt.date(2032, 6, 1)  # the day after the season ends; the tick runs it on 1 June
YOUTH = make_development_config().youth


def test_rollover_intake__is_the_age_asked_for_on_the_rollover_day() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        players = uow.players.all()
    intake = [
        p
        for p in players
        if p.is_youth and p.contract is not None and p.contract.start == ROLLOVER_DAY
    ]
    assert intake
    low, high = YOUTH.intake_age
    assert all(low <= p.age_on(ROLLOVER_DAY) <= high for p in intake)
    assert all(p.contract.end == contract_end(ROLLOVER_DAY, YOUTH.contract_years) for p in intake)  # type: ignore[union-attr]
