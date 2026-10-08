from dataclasses import replace

from footystreams.domain.manager import SubHabits
from footystreams.sim.config_manager import ManagerConfig
from footystreams.sim.manager_assess import Assessment, assess
from footystreams.sim.manager_plans import candidate_plans, choose_plan
from footystreams.sim.rng import SimRng
from footystreams.sim.state import PlayerState
from tests.factories.sim_play import make_play

CFG = ManagerConfig()
HABITS = SubHabits(
    earliest_minute=55,
    aggressiveness=0.5,
    fresh_legs_bias=0.5,
    protect_lead_bias=0.5,
    chase_game_bias=0.5,
    reacts_to_cards=0.5,
)


def _players() -> list[PlayerState]:
    return make_play().state.home.players[1:]


def _view(
    *,
    minute: float = 30.0,
    margin: int = 0,
    men_difference: int = 0,
    tired: tuple[tuple[float, PlayerState], ...] | None = None,
    booked: tuple[PlayerState, ...] = (),
) -> Assessment:
    seen = tired if tired is not None else tuple((0.1, player) for player in _players()[:3])
    return Assessment(minute, margin, men_difference, seen, booked)


def _reasons(view: Assessment, seen: int = 0) -> list[str]:
    return [plan.reason for plan in candidate_plans(view, HABITS, seen, CFG)]


def test_assess__reads_the_score_the_clock_and_ranks_the_tired() -> None:
    state = make_play().state
    state.home.score = 2
    state.t_period = 3000.0
    state.home.players[3].exhaustion = 0.9
    view = assess(state, "home", SimRng(1), CFG)
    assert (view.margin, view.minute, view.men_difference) == (2, 50.0, 0)
    assert view.tired[0][1] is state.home.players[3]
    assert [entry[0] for entry in view.tired] == sorted((e[0] for e in view.tired), reverse=True)


def test_assess__a_manager_with_perfect_sense_reads_exhaustion_exactly() -> None:
    state = make_play().state
    state.home.players[4].exhaustion = 0.5
    view = assess(state, "home", SimRng(2), ManagerConfig(noise_scale=0.0))
    assert view.tired[0] == (0.5, state.home.players[4])


def test_candidate_plans__a_calm_early_match_offers_nothing() -> None:
    assert _reasons(_view()) == []


def test_candidate_plans__tired_legs_late_offer_a_fresh_legs_change() -> None:
    tired = ((0.8, _players()[0]),)
    assert _reasons(_view(minute=65.0, tired=tired)) == ["fresh_legs"]
    assert _reasons(_view(minute=40.0, tired=tired)) == []


def test_candidate_plans__trailing_late_chases_and_leading_late_protects() -> None:
    chase = candidate_plans(_view(minute=70.0, margin=-1), HABITS, 0, CFG)
    protect = candidate_plans(_view(minute=80.0, margin=1), HABITS, 0, CFG)
    assert [(plan.reason, plan.rungs) for plan in chase] == [("chase_game", 1)]
    assert [(plan.reason, plan.rungs) for plan in protect] == [("protect_lead", -1)]
    assert _reasons(_view(minute=50.0, margin=-1)) == []


def test_candidate_plans__a_new_dismissal_is_reacted_to_once() -> None:
    assert _reasons(_view(men_difference=-1)) == ["dismissal"]
    assert _reasons(_view(men_difference=-1), seen=-1) == []
    assert _reasons(_view(men_difference=1)) == ["opponent_dismissal"]


def test_candidate_plans__a_dismissal_while_trailing_keeps_the_mentality() -> None:
    plan = candidate_plans(_view(men_difference=-1, margin=-1), HABITS, 0, CFG)[0]
    assert plan.rungs == 0


def test_candidate_plans__a_booked_aggressive_player_is_a_yellow_risk() -> None:
    player = _players()[0]
    player.skills = replace(player.skills, aggression=80.0)
    assert _reasons(_view(booked=(player,), minute=65.0)) == ["yellow_risk"]
    assert _reasons(_view(booked=(player,), minute=30.0)) == []  # not before the hour
    assert _reasons(_view(booked=(player,), minute=88.0)) == []


def test_choose_plan__nothing_to_choose_means_do_nothing() -> None:
    assert choose_plan([], SimRng(1), CFG) is None


def test_choose_plan__a_heavy_plan_is_usually_chosen_over_staying() -> None:
    plans = candidate_plans(_view(minute=70.0, margin=-2), HABITS, 0, CFG)
    chosen = [choose_plan(plans, SimRng(seed), CFG) for seed in range(40)]
    assert sum(plan is not None for plan in chosen) > 10
    assert any(plan is None for plan in chosen)
