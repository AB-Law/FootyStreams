from footystreams.events.open_play import DribbleEvent, PassEvent, ShotEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.enrich import dribble_fields, pass_fields, shot_fields
from footystreams.sim.options import ActionKind, Option
from footystreams.sim.play import Play
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import context_result

ON = merge_config(SimConfig(), {"context": {"enabled": True}})
OFF = merge_config(SimConfig(), {"context": {"enabled": False}})


def _option(end: tuple[float, float]) -> Option:
    return Option(ActionKind.PASS, 0.5, 0.8, end, 0.1)


def _play(config: SimConfig) -> Play:
    return make_play(config=config)  # home attacks +x


def test_pass_fields__off_records_nothing() -> None:
    assert pass_fields(_play(OFF), (0.4, 0.5), _option((0.7, 0.5))) == {}
    assert dribble_fields(_play(OFF), _option((0.5, 0.5)), kept_ball=True) == {}
    off = _play(OFF)
    assert shot_fields(off, 0.9, off.state.carrier, "goal") == {}


def test_pass_fields__a_long_forward_pass_is_progressive_and_gains_threat() -> None:
    fields = pass_fields(_play(ON), (0.4, 0.5), _option((0.8, 0.5)))
    assert fields["progressive"] is True
    assert fields["xt_gain"] > 0.0  # type: ignore[operator]
    assert fields["end_pos"] == {"x": 0.8, "y": 0.5}


def test_pass_fields__a_short_or_backward_pass_is_not_progressive() -> None:
    short = pass_fields(_play(ON), (0.4, 0.5), _option((0.5, 0.5)))
    back = pass_fields(_play(ON), (0.6, 0.5), _option((0.3, 0.5)))
    assert short["progressive"] is False
    assert back["progressive"] is False
    assert back["xt_gain"] < 0.0  # type: ignore[operator]


def test_dribble_fields__only_a_kept_ball_has_an_end() -> None:
    play = _play(ON)
    assert "end_pos" not in dribble_fields(play, _option((0.6, 0.4)), kept_ball=False)
    kept = dribble_fields(play, _option((0.6, 0.4)), kept_ball=True)
    assert kept["end_pos"] == {"x": 0.6, "y": 0.4}


def test_dribble_fields__records_how_the_take_on_was_done_and_nothing_with_context_off() -> None:
    assert "skill_move" in dribble_fields(_play(ON), _option((0.6, 0.4)), kept_ball=True)
    assert dribble_fields(_play(OFF), _option((0.6, 0.4)), kept_ball=True) == {}


def test_shot_fields__big_chance_starts_at_the_configured_xg() -> None:
    play = _play(ON)
    shooter = play.state.carrier
    assert shot_fields(play, 0.29, shooter, "goal")["big_chance"] is False
    assert shot_fields(play, 0.30, shooter, "goal")["big_chance"] is True


def test_shot_fields__a_shot_is_taken_with_the_foot_unless_it_is_a_header() -> None:
    play = _play(ON)
    shooter = play.state.carrier
    assert shot_fields(play, 0.1, shooter, "saved")["body_part"] == "foot"
    assert shot_fields(play, 0.1, shooter, "saved", header=True)["body_part"] == "head"
    assert shot_fields(_play(OFF), 0.1, shooter, "saved", header=True) == {}


def test_run_match__headers_come_only_from_corners_and_everything_else_is_a_foot_shot() -> None:
    shots = [
        e
        for seed in range(6)
        for e in run_match(make_demo_setup(), seed, SimConfig(), default_tables()).events
        if isinstance(e, ShotEvent)
    ]
    heads = [shot for shot in shots if shot.body_part == "head"]
    assert shots
    assert heads, "corners are met in the air within six matches"
    assert all(shot.body_part in ("foot", "head") for shot in shots)
    assert len(heads) < len(shots) / 2


def test_run_match__enriched_events_carry_their_fields() -> None:
    events = context_result().events
    passes = [e for e in events if isinstance(e, PassEvent)]
    assert passes
    assert all(e.end_pos is not None for e in passes)
    assert any(e.progressive for e in passes)
    assert any(e.xt_gain != 0.0 for e in passes)
    shots = [e for e in events if isinstance(e, ShotEvent)]
    assert all(e.big_chance == (e.xg >= 0.3) for e in shots)
    dribbles = [e for e in events if isinstance(e, DribbleEvent)]
    assert all((e.end_pos is not None) == (e.outcome == "success") for e in dribbles)
