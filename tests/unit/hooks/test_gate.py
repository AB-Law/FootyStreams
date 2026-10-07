"""Tests for the end-of-turn quality gate hook (tools/hooks/gate.py)."""

import io
import json
import sys
from pathlib import Path
from typing import Protocol

import pytest

from tools.hooks import gate

PYTHON = Path(sys.executable).as_posix()
PASSING = f'{PYTHON} -c "print(1)"'
FAILING = f"{PYTHON} -c \"import sys; print('ruff: boom'); sys.exit(1)\""
Outcome = tuple[int, str, str]


class GateRunner(Protocol):
    """Runs the hook for an agent and returns (exit code, stdout, stderr)."""

    def __call__(self, agent: str = ..., payload: str = ...) -> Outcome:
        """Run the hook."""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway project that looks set up (has pyproject.toml) with one watched file."""
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("FOOTY_GATE_ROOT", str(tmp_path))
    monkeypatch.setenv("FOOTY_GATE_COMMAND", PASSING)
    monkeypatch.delenv("FOOTY_GATE_MAX_RETRIES", raising=False)
    return tmp_path


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> GateRunner:
    """Run the hook as an agent would and return (exit code, stdout, stderr)."""

    def _run(agent: str = "claude", payload: str = "{}") -> Outcome:
        monkeypatch.setattr(sys, "argv", ["gate.py", "--agent", agent])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        code = gate.main()
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def test_gate__project_not_set_up_yet__passes_silently(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "pyproject.toml").unlink()
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)

    assert run() == (0, "", "")


def test_gate__failing_checks_for_claude__block_with_the_report(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)

    code, _, err = run("claude")

    assert code == gate.CLAUDE_BLOCK_EXIT_CODE
    assert "QUALITY GATE FAILED (attempt 1 of 8)" in err
    assert "ruff: boom" in err


def test_gate__failing_checks_for_cursor__ask_for_a_followup_and_exit_zero(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)

    code, out, _ = run("cursor", '{"status": "completed", "loop_count": 0}')

    assert code == 0
    assert "ruff: boom" in json.loads(out)["followup_message"]


def test_gate__cursor_turn_that_was_aborted__is_not_gated(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)

    assert run("cursor", '{"status": "aborted"}') == (0, "{}\n", "")


def test_gate__passing_checks__pass_and_remember_the_green_state(
    project: Path, run: GateRunner
) -> None:
    assert run() == (0, "", "")
    assert (project / ".gate" / "last_green").exists()


def test_gate__nothing_changed_since_green__skips_the_checks(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    run()
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)  # would fail if it actually ran

    assert run() == (0, "", "")


def test_gate__file_changed_since_green__runs_the_checks_again(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    run()
    (project / "src" / "module.py").write_text("x = 2  # changed\n", encoding="utf-8")
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)

    code, _, _ = run()

    assert code == gate.CLAUDE_BLOCK_EXIT_CODE


def test_gate__missing_command__blocks_and_says_why(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", "definitely-not-a-command")

    code, _, err = run()

    assert code == gate.CLAUDE_BLOCK_EXIT_CODE
    assert "command not found" in err


def test_gate__command_that_hangs__blocks_after_the_timeout(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", f'{PYTHON} -c "import time; time.sleep(30)"')
    monkeypatch.setenv("FOOTY_GATE_TIMEOUT_S", "1")

    code, _, err = run()

    assert code == gate.CLAUDE_BLOCK_EXIT_CODE
    assert "timed out after 1s" in err


def test_gate__retry_cap__gives_up_loudly_then_starts_counting_again(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)
    monkeypatch.setenv("FOOTY_GATE_MAX_RETRIES", "2")

    assert run()[0] == gate.CLAUDE_BLOCK_EXIT_CODE
    assert run()[0] == gate.CLAUDE_BLOCK_EXIT_CODE
    code, out, _ = run()

    assert code == 0  # gave up, but loudly:
    assert "STILL FAILING after 2 attempts" in json.loads(out)["systemMessage"]
    assert run()[0] == gate.CLAUDE_BLOCK_EXIT_CODE  # the counter restarted


def test_gate__zero_max_retries__never_gives_up(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)
    monkeypatch.setenv("FOOTY_GATE_MAX_RETRIES", "0")

    codes = [run()[0] for _ in range(12)]

    assert set(codes) == {gate.CLAUDE_BLOCK_EXIT_CODE}


def test_gate__a_pass_resets_the_failure_counter(
    project: Path, run: GateRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOOTY_GATE_COMMAND", FAILING)
    run()
    monkeypatch.setenv("FOOTY_GATE_COMMAND", PASSING)
    (project / "src" / "module.py").write_text("x = 3\n", encoding="utf-8")
    run()

    assert gate.read_counter(project / ".gate") == 0


def test_fingerprint__ignores_caches_and_changes_when_a_watched_file_changes(project: Path) -> None:
    before = gate.fingerprint(project)
    (project / "src" / "__pycache__").mkdir()
    (project / "src" / "__pycache__" / "m.pyc").write_bytes(b"cache")
    (project / ".gate").mkdir()
    (project / ".gate" / "last_green").write_text("x", encoding="utf-8")

    assert gate.fingerprint(project) == before

    (project / "src" / "new.py").write_text("y = 1\n", encoding="utf-8")
    assert gate.fingerprint(project) != before


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", '"string"'])
def test_read_hook_payload__tolerates_garbage(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))

    assert gate.read_hook_payload() == {}


def test_read_counter__missing_or_corrupt_file__is_zero(tmp_path: Path) -> None:
    assert gate.read_counter(tmp_path) == 0
    (tmp_path / "fail_count").write_text("garbage", encoding="utf-8")
    assert gate.read_counter(tmp_path) == 0
