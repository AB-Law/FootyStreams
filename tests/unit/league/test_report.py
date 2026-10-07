from __future__ import annotations

from footystreams.league.report import format_money, format_table
from tests.factories.league_run import cached_small_season


def test_format_table__lists_every_club_best_first_with_the_columns() -> None:
    result, factory = cached_small_season()
    with factory() as uow:
        names = {club.id: club.name for club in uow.clubs.all()}
    lines = format_table(result.table, names).splitlines()
    assert lines[0].split()[-1] == "Pts"
    assert len(lines) == 1 + len(result.table)
    assert names[result.table[0].club_id] in lines[1]


def test_format_money__shows_balance_and_change_in_millions() -> None:
    _, factory = cached_small_season()
    with factory() as uow:
        clubs = uow.clubs.all()
    opening = {club.id: club.finances.balance - 2_000_000 for club in clubs}
    text = format_money(clubs, opening)
    assert "+2.0m" in text
    assert text.splitlines()[0].split() == ["Club", "Balance", "Change"]
