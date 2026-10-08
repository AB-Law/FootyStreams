import json
import subprocess
import sys
from pathlib import Path

import pytest

from footystreams.cli.sim import main
from footystreams.events.clock import match_clock
from footystreams.events.types import MATCH_EVENT_ADAPTER
from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.sim.render import (
    Verbosity,
    clock_text,
    is_key_event,
    names_for,
    render_event,
    render_events,
    render_summary,
)
from footystreams.tools.paths import PROJECT_ROOT
from tests.factories.sim_teams import make_demo_setup

SETUP = make_demo_setup()
RESULT = run_match(SETUP, 7, SimConfig(), default_tables())
NAMES = names_for(SETUP)


@pytest.mark.parametrize(
    ("period", "elapsed", "text"), [(1, 61, "1'"), (1, 2700 + 130, "45+2'"), (2, 2400, "85'")]
)
def test_clock_text__regulation_and_stoppage(period: int, elapsed: int, text: str) -> None:
    assert clock_text(match_clock(period, elapsed)) == text


def test_render_events__full_prints_every_event_but_the_summary() -> None:
    lines = list(render_events(RESULT.events, NAMES, Verbosity.FULL))
    assert len(lines) == len(RESULT.events) - 1


def test_render_events__key_prints_fewer_lines_and_all_structure_events() -> None:
    key = list(render_events(RESULT.events, NAMES, Verbosity.KEY))
    full = list(render_events(RESULT.events, NAMES, Verbosity.FULL))
    assert 0 < len(key) < len(full)
    assert any("Kick-off" in line for line in key)
    assert any("Full-time" in line for line in key)


def test_render_event__goal_line_names_the_scorer_club_and_score() -> None:
    goal = next(event for event in RESULT.events if event.type == "goal")
    line = render_event(goal, NAMES)
    assert "GOAL!" in line
    assert "KES" in line or "HAR" in line
    assert " 1-0 " in line or " 0-1 " in line


def test_is_key_event__passes_are_not_key_and_goals_are() -> None:
    passes = [e for e in RESULT.events if e.type == "pass"]
    assert not any(is_key_event(e) for e in passes)
    assert is_key_event(RESULT.events[0])


def test_render_summary__has_a_final_line_and_one_row_per_statistic() -> None:
    lines = render_summary(RESULT.summary, NAMES)
    assert lines[0].startswith("Final: KES")
    assert any(line.startswith("Possession") for line in lines)
    assert len(lines) == 12


def test_main__text_output_ends_with_the_summary_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert "Kick-off (first half)" in out
    assert "Final: KES" in out


def test_main__ndjson_lines_are_valid_events_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--seed", "3", "--format", "ndjson"]) == 0
    lines = capsys.readouterr().out.splitlines()
    events = [MATCH_EVENT_ADAPTER.validate_python(json.loads(line)) for line in lines]
    assert [e.seq for e in events] == list(range(len(events)))
    assert events[-1].type == "match_summary"


def test_main__without_demo_explains_what_is_missing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "--demo" in capsys.readouterr().err


def test_main__is_deterministic_per_seed(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--seed", "5", "--format", "ndjson"])
    first = capsys.readouterr().out
    main(["--demo", "--seed", "5", "--format", "ndjson"])
    assert capsys.readouterr().out == first


def test_sim_command__runs_as_a_real_process_from_another_directory(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "footystreams.cli.sim", "--demo", "--seed", "7"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Final: KES" in completed.stdout
    assert PROJECT_ROOT.exists()
