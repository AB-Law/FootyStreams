from dataclasses import replace

from footystreams.sim.effective import Skills
from footystreams.sim.skill_moves import SkillMove, choose_skill_move, move_weights, skill_level
from tests.factories.sim_play import make_state

SHOWY = (SkillMove.STEP_OVER, SkillMove.ROULETTE, SkillMove.RAINBOW_FLICK, SkillMove.NUTMEG)


def _skills(**changes: float) -> Skills:
    base = make_state().home.players[9].skills
    return replace(base, **changes)


def _gifted() -> Skills:
    return _skills(dribbling=95.0, flair=95.0, agility=95.0, balance=90.0, pace=80.0)


def _plain() -> Skills:
    return _skills(dribbling=25.0, flair=20.0, agility=30.0, balance=40.0, pace=50.0)


def _showy_count(skills: Skills, gap: float | None) -> int:
    moves = (choose_skill_move(skills, gap, 0.5, 0.3, tick) for tick in range(400))
    return sum(move in SHOWY for move in moves)


def test_skill_level__rises_with_dribbling_flair_and_agility() -> None:
    assert skill_level(_gifted()) > skill_level(_plain())
    assert 0.0 <= skill_level(_plain()) <= skill_level(_gifted()) <= 1.0


def test_move_weights__with_nobody_near_there_is_nothing_to_beat() -> None:
    weights = move_weights(_gifted(), None, 0.0, 0.5)
    assert weights[SkillMove.STEP_OVER] == 0.0
    assert weights[SkillMove.NUTMEG] == 0.0
    assert weights[SkillMove.ROULETTE] == 0.0
    assert weights[SkillMove.KNOCK_PAST] > 0.0


def test_move_weights__a_nutmeg_needs_the_defender_close() -> None:
    assert move_weights(_gifted(), 5.0, 0.5, 0.5)[SkillMove.NUTMEG] == 0.0
    assert move_weights(_gifted(), 1.5, 0.5, 0.5)[SkillMove.NUTMEG] > 0.0


def test_move_weights__a_wide_player_cuts_inside_more_than_a_central_one() -> None:
    wide = move_weights(_gifted(), 2.0, 0.3, 0.05)[SkillMove.CUT_INSIDE]
    central = move_weights(_gifted(), 2.0, 0.3, 0.5)[SkillMove.CUT_INSIDE]
    assert wide > central == 0.0


def test_move_weights__a_quick_player_with_room_knocks_it_past() -> None:
    quick = move_weights(_skills(pace=95.0), 5.5, 0.1, 0.5)[SkillMove.KNOCK_PAST]
    slow = move_weights(_skills(pace=20.0), 5.5, 0.1, 0.5)[SkillMove.KNOCK_PAST]
    assert quick > slow


def test_choose_skill_move__a_gifted_dribbler_tries_far_more_showy_moves_than_a_plain_one() -> None:
    assert _showy_count(_gifted(), 1.5) > 3 * _showy_count(_plain(), 1.5)


def test_choose_skill_move__is_a_pure_function_of_its_inputs() -> None:
    args = (_gifted(), 2.0, 0.4, 0.2, 17)
    assert choose_skill_move(*args) == choose_skill_move(*args)


def test_choose_skill_move__varies_with_the_tick_so_a_player_does_not_repeat_himself() -> None:
    moves = {choose_skill_move(_gifted(), 2.0, 0.4, 0.2, tick) for tick in range(60)}
    assert len(moves) >= 4
