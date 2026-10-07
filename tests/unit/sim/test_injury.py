from collections.abc import Callable
from dataclasses import replace

from footystreams.domain.types import Position
from footystreams.events.discipline import InjuryEvent, SubstitutionEvent
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, merge_config
from footystreams.sim.injury import (
    Incident,
    hazard_multiplier,
    injure,
)
from footystreams.sim.play import Play
from footystreams.sim.state import PlayerState
from footystreams.sim.weather import NEUTRAL
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import make_demo_setup

ON = {"injury": {"enabled": True, "minor_off_share": 1.0}}
FIRST_SEEDS = range(1, 60)


def _config(extra: dict[str, object] | None = None) -> SimConfig:
    return merge_config(merge_config(SimConfig(), ON), extra or {})


def _events(play: Play) -> list[MatchEvent]:
    return list(play.emit.events)


def _outfielder(play: Play) -> PlayerState:
    return next(p for p in play.state.home.players if p.position is not Position.GK)


def _find_leaving_injury(prepare: Callable[[Play], None]) -> tuple[Play, PlayerState]:
    """Return a fresh play and a victim after an injury that takes the player off."""
    for seed in FIRST_SEEDS:
        play = make_play(seed=seed, setup=make_demo_setup(), config=_config())
        prepare(play)
        victim = _outfielder(play)
        injure(play, Incident(victim, "contact", None, None))
        injuries = [e for e in _events(play) if isinstance(e, InjuryEvent)]
        if not injuries[-1].can_continue:
            return play, victim
    raise AssertionError("no seed produced an injury that takes the player off")


def _keep_bench(play: Play) -> None:
    del play


def _empty_bench(play: Play) -> None:
    play.state.home.bench.clear()


def test_hazard_multiplier__tiredness_proneness_and_a_wet_pitch_all_raise_the_hazard() -> None:
    player = _outfielder(make_play(setup=make_demo_setup()))
    cfg = SimConfig().injury
    rested = hazard_multiplier(player, NEUTRAL, cfg)
    player.exhaustion = 0.8
    assert hazard_multiplier(player, NEUTRAL, cfg) > rested
    player.exhaustion = 0.0
    player.skills = replace(player.skills, injury_proneness=player.skills.injury_proneness + 30)
    assert hazard_multiplier(player, NEUTRAL, cfg) > rested
    wet = replace(NEUTRAL, injury_mult=1.2)
    assert hazard_multiplier(player, wet, cfg) > hazard_multiplier(player, NEUTRAL, cfg)


def test_injure__a_player_who_cannot_continue_is_replaced_in_a_forced_change() -> None:
    play, victim = _find_leaving_injury(_keep_bench)
    events = _events(play)
    injury, change = events[-2], events[-1]
    assert isinstance(injury, InjuryEvent)
    assert isinstance(change, SubstitutionEvent)
    assert change.player_off_id == victim.player_id
    assert change.reason == "injury"
    assert play.state.home.subs_used == 1
    assert play.state.home.windows_used == 0
    assert len(play.state.injury_log) == 1


def test_injure__with_nobody_on_the_bench_the_side_plays_short() -> None:
    play, victim = _find_leaving_injury(_empty_bench)
    assert len(play.state.home.players) == 10
    assert victim not in play.state.home.players
    assert victim in play.state.home.substituted_off
    assert not any(isinstance(e, SubstitutionEvent) for e in _events(play))
    assert _events(play)[-1].ctx.men_home == 10


def test_injure__a_hurt_carrier_hands_the_ball_to_a_teammate() -> None:
    play = make_play(seed=3, setup=make_demo_setup(), config=_config())
    play.state.home.bench.clear()
    victim = _outfielder(play)
    play.state.carrier = victim
    for _ in range(40):
        if victim not in play.state.home.players:
            break
        injure(play, Incident(victim, "contact", None, None))
    assert play.state.carrier is not victim
    assert play.state.carrier in play.state.home.players


def test_injure__a_side_at_the_minimum_keeps_the_hurt_player_on() -> None:
    config = _config({"discipline": {"min_players": 11}})
    play = make_play(seed=4, setup=make_demo_setup(), config=config)
    play.state.home.bench.clear()
    victim = _outfielder(play)
    for _ in range(10):
        injure(play, Incident(victim, "contact", None, None))
    assert len(play.state.home.players) == 11
    assert all(e.can_continue for e in _events(play) if isinstance(e, InjuryEvent))


def test_injure__a_hurt_goalkeeper_without_cover_leaves_an_outfielder_in_goal() -> None:
    for seed in FIRST_SEEDS:
        play = make_play(seed=seed, setup=make_demo_setup(), config=_config())
        play.state.home.bench.clear()
        keeper = play.state.home.keeper
        injure(play, Incident(keeper, "non_contact", None, None))
        if keeper not in play.state.home.players:
            break
    assert play.state.home.keeper is not keeper
    assert play.state.home.keeper.position is Position.GK
