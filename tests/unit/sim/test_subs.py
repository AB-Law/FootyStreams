from footystreams.domain.types import PlayerId, Position
from footystreams.events.discipline import SubstitutionEvent
from footystreams.sim.actions.cards import dismiss
from footystreams.sim.config import ManagerConfig
from footystreams.sim.play import Play
from footystreams.sim.state import TeamState
from footystreams.sim.subs import (
    Window,
    can_change,
    is_keeper,
    make_substitution,
    replacement_for,
)
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import make_demo_setup

CFG = ManagerConfig()


def _play() -> Play:
    return make_play(setup=make_demo_setup())


def _bench_keeper(team: TeamState) -> PlayerId:
    return next(pid for pid in team.bench if is_keeper(team, pid))


def test_is_keeper__only_the_bench_goalkeeper_is_one() -> None:
    team = _play().state.home
    assert [is_keeper(team, pid) for pid in team.bench] == [True, False, False]


def test_can_change__needs_subs_a_bench_and_an_open_or_unused_window() -> None:
    team = _play().state.home
    assert can_change(team, 3000.0, Window.PLAY, CFG)
    team.subs_used = CFG.max_subs
    assert not can_change(team, 3000.0, Window.FORCED, CFG)
    team.subs_used = 0
    team.windows_used = CFG.max_windows
    assert not can_change(team, 3000.0, Window.PLAY, CFG)
    assert can_change(team, 3000.0, Window.FORCED, CFG)
    assert can_change(team, 3000.0, Window.HALFTIME, CFG)


def test_can_change__a_change_inside_an_open_window_does_not_need_a_new_one() -> None:
    team = _play().state.home
    team.windows_used = CFG.max_windows
    team.last_window_s = 3000.0
    assert can_change(team, 3010.0, Window.PLAY, CFG)
    assert not can_change(team, 3100.0, Window.PLAY, CFG)


def test_can_change__empty_bench_blocks_everything() -> None:
    team = _play().state.home
    team.bench.clear()
    assert not can_change(team, 0.0, Window.FORCED, CFG)


def test_replacement_for__outfield_never_uses_a_bench_goalkeeper() -> None:
    team = _play().state.home
    outfielder = team.players[8]
    chosen = replacement_for(team, outfielder)
    assert chosen is not None
    assert not is_keeper(team, chosen)


def test_replacement_for__a_goalkeeper_is_replaced_by_the_bench_keeper() -> None:
    team = _play().state.home
    assert replacement_for(team, team.keeper) == _bench_keeper(team)


def test_replacement_for__nobody_when_only_keepers_remain_for_an_outfield_slot() -> None:
    team = _play().state.home
    team.bench = [_bench_keeper(team)]
    assert replacement_for(team, team.players[8]) is None


def test_replacement_for__prefers_the_better_fit_for_the_slot() -> None:
    team = _play().state.home
    striker_slot = team.players[10]
    chosen = replacement_for(team, striker_slot)
    assert team.sheet.squad[chosen].position_competence[Position.ST] == 90  # type: ignore[index]


def test_make_substitution__swaps_players_updates_lists_and_emits_the_event() -> None:
    play = _play()
    team = play.state.home
    off = team.players[8]
    on_id = replacement_for(team, off)
    assert on_id is not None
    seconds = make_substitution(play, off, on_id, "tactical", Window.PLAY)
    event = play.emit.events[0]
    assert isinstance(event, SubstitutionEvent)
    assert (event.player_off_id, event.player_on_id, event.reason) == (
        off.player_id,
        on_id,
        "tactical",
    )
    assert off not in team.players
    assert team.players[8].player_id == on_id
    assert team.players[8].slot == off.slot
    assert on_id not in team.bench
    assert team.substituted_off == [off]
    assert (team.subs_used, team.windows_used) == (1, 1)
    assert seconds > 15.0
    assert play.state.stoppage_s == seconds


def test_make_substitution__two_changes_in_one_stoppage_share_a_window() -> None:
    play = _play()
    team = play.state.home
    for slot in (8, 9):
        off = team.players[slot]
        make_substitution(play, off, replacement_for(team, off), "tactical", Window.PLAY)  # type: ignore[arg-type]
    assert (team.subs_used, team.windows_used) == (2, 1)


def test_make_substitution__halftime_and_forced_changes_do_not_use_a_window() -> None:
    play = _play()
    team = play.state.home
    off = team.players[8]
    make_substitution(play, off, replacement_for(team, off), "tactical", Window.HALFTIME)  # type: ignore[arg-type]
    assert team.windows_used == 0


def test_make_substitution__the_carrier_is_replaced_in_possession() -> None:
    play = _play()
    team = play.state.home
    off = play.state.carrier
    make_substitution(play, off, replacement_for(team, off), "injury", Window.FORCED)  # type: ignore[arg-type]
    assert play.state.carrier is not off
    assert play.state.carrier.player_id not in {p.player_id for p in team.substituted_off}


def test_make_substitution__a_substitute_is_fresh_and_in_the_same_formation_slot() -> None:
    play = _play()
    team = play.state.home
    off = team.players[10]
    on_id = replacement_for(team, off)
    make_substitution(play, off, on_id, "fatigue", Window.PLAY)  # type: ignore[arg-type]
    newcomer = team.players[10]
    assert (newcomer.base_x, newcomer.base_y) == (off.base_x, off.base_y)
    assert newcomer.position is off.position


def test_make_substitution__a_bench_keeper_takes_over_goal_from_an_emergency_keeper() -> None:
    play = _play()
    team = play.state.home
    bench_keeper = _bench_keeper(team)
    dismiss(team, team.keeper)
    stand_in = team.keeper
    make_substitution(play, stand_in, bench_keeper, "injury", Window.FORCED)
    assert [p.position for p in team.players].count(Position.GK) == 1
    assert team.keeper.player_id == bench_keeper
    assert team.keeper.slot == stand_in.slot
    assert (team.keeper.base_x, team.keeper.base_y) == (stand_in.base_x, stand_in.base_y)
