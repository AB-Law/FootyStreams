"""A substitute who comes on in first-half stoppage time must not get negative minutes.

`match_elapsed_s` counts the first half as exactly 2,700 s, so a change made 242 s into first-half
stoppage (clock 2,942) and a dismissal 120 s into the second half (clock 2,820) looked like the
player leaving before he arrived: minutes of -1, and a validation error that lost the whole
summary of the match (found by the 1,200-match balance run, seed 284 of the default world).
"""

from __future__ import annotations

from footystreams.events.derive.presence import player_spells
from footystreams.events.discipline import CardEvent, SubstitutionEvent
from footystreams.events.open_play import PassEvent
from tests.factories.log_builder import LogBuilder
from tests.factories.sim_teams import make_demo_setup

SETUP = make_demo_setup()
STARTER = SETUP.home.lineup[3].player_id
SUBSTITUTE = SETUP.home.bench[1]
FIRST_HALF_S = 45 * 60 + 242  # 45 minutes and 4 minutes 2 seconds of stoppage
SECOND_HALF_S = 45 * 60


def _log() -> LogBuilder:
    log = LogBuilder()
    log.add(
        SubstitutionEvent,
        player_off_id=STARTER,
        player_on_id=SUBSTITUTE,
        period=1,
        minute=45,
        second=2,
        stoppage=4,
    )
    log.add(CardEvent, player_id=SUBSTITUTE, colour="red", period=2, minute=47)
    log.add(PassEvent, from_player_id=STARTER, period=2, minute=90)
    return log


def test_player_spells__a_dismissal_after_a_stoppage_time_change_follows_the_change() -> None:
    spells = player_spells(_log().events, SETUP, FIRST_HALF_S + SECOND_HALF_S)

    spell = spells[SUBSTITUTE]
    assert spell.end_s > spell.start_s
    assert spell.minutes == 2  # two minutes of the second half, none of the first


def test_player_spells__the_starter_replaced_in_stoppage_played_the_whole_first_half() -> None:
    spells = player_spells(_log().events, SETUP, FIRST_HALF_S + SECOND_HALF_S)

    assert spells[STARTER].end_s == FIRST_HALF_S
    assert spells[STARTER].minutes == 49
