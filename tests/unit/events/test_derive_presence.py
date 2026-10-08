from footystreams.events.derive.presence import injured_players, leaver, player_spells
from footystreams.events.discipline import CardEvent, InjuryEvent, SubstitutionEvent
from footystreams.events.open_play import PassEvent
from tests.factories.log_builder import LogBuilder
from tests.factories.sim_teams import make_demo_setup

SETUP = make_demo_setup()
STARTERS = [slot.player_id for slot in SETUP.home.lineup]
BENCH = list(SETUP.home.bench)
MATCH_END_S = 5400


def _spells(log: LogBuilder) -> dict[str, tuple[int, int, bool]]:
    spells = player_spells(log.events, SETUP, MATCH_END_S)
    return {pid: (spell.start_s, spell.end_s, spell.started) for pid, spell in spells.items()}


def test_player_spells__starters_play_the_whole_match_by_default() -> None:
    spells = _spells(LogBuilder())
    assert spells[STARTERS[3]] == (0, MATCH_END_S, True)
    assert BENCH[0] not in spells
    assert len(spells) == 22


def test_player_spells__a_substitution_ends_one_spell_and_starts_the_next() -> None:
    log = LogBuilder()
    log.add(SubstitutionEvent, player_off_id=STARTERS[3], player_on_id=BENCH[1], minute=60)
    spells = _spells(log)
    assert spells[STARTERS[3]] == (0, 3600, True)
    assert spells[BENCH[1]] == (3600, MATCH_END_S, False)


def test_player_spells__a_dismissal_ends_the_spell_without_a_replacement() -> None:
    log = LogBuilder()
    log.add(CardEvent, player_id=STARTERS[4], colour="red", minute=30)
    assert _spells(log)[STARTERS[4]] == (0, 1800, True)


def test_leaver__an_injury_followed_by_its_change_is_the_changes_departure() -> None:
    log = LogBuilder()
    log.add(InjuryEvent, player_id=STARTERS[5], can_continue=False)
    log.add(SubstitutionEvent, player_off_id=STARTERS[5], player_on_id=BENCH[1], reason="injury")
    assert leaver(log.events, 0) is None
    assert leaver(log.events, 1) == STARTERS[5]


def test_leaver__an_unreplaced_injury_takes_the_player_off() -> None:
    log = LogBuilder()
    log.add(InjuryEvent, player_id=STARTERS[5], can_continue=False, minute=70)
    log.add(PassEvent, from_player_id=STARTERS[6], minute=71)
    assert leaver(log.events, 0) == STARTERS[5]
    assert _spells(log)[STARTERS[5]] == (0, 4200, True)


def test_leaver__a_hurt_player_who_carries_on_stays() -> None:
    log = LogBuilder()
    log.add(InjuryEvent, player_id=STARTERS[5], can_continue=True)
    assert leaver(log.events, 0) is None


def test_injured_players__lists_every_victim() -> None:
    log = LogBuilder()
    log.add(InjuryEvent, player_id=STARTERS[5], can_continue=True)
    log.add(InjuryEvent, player_id=STARTERS[7], can_continue=False)
    assert injured_players(log.events) == {STARTERS[5], STARTERS[7]}


def test_spell__minutes_round_to_the_nearest() -> None:
    spells = player_spells(LogBuilder().events, SETUP, 5370)
    assert spells[STARTERS[0]].minutes == 90
