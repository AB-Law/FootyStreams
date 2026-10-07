import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from footystreams.tools import check
from footystreams.tools.check import (
    COVERAGE_TEST_STEP,
    FAST_TEST_STEP,
    LINT_STEPS,
    CheckStep,
    StepResult,
    Tier,
    format_report,
    main,
    parse_tier,
    run_step,
    run_steps,
    steps_for,
)


def _result(name: str, returncode: int, output: str = "") -> StepResult:
    return StepResult(CheckStep(name, ("noop",)), returncode, 0.5, output)


def test_run_steps__a_failing_step__does_not_stop_later_steps() -> None:
    steps = [CheckStep("first", ("a",)), CheckStep("second", ("b",))]
    returncodes = {"first": 1, "second": 0}

    results = run_steps(steps, runner=lambda step: _result(step.name, returncodes[step.name]))

    assert [result.step.name for result in results] == ["first", "second"]
    assert [result.passed for result in results] == [False, True]


def test_format_report__all_pass__says_passed_and_hides_output() -> None:
    report = format_report([_result("ruff", 0, "noisy output")])

    assert "[PASS] ruff" in report
    assert "noisy output" not in report
    assert report.endswith("quality gate: PASSED")


def test_format_report__failure__shows_output_and_counts_failures() -> None:
    report = format_report([_result("mypy", 1, "error: bad type"), _result("ruff", 0)])

    assert "[FAIL] mypy" in report
    assert "    error: bad type" in report
    assert report.endswith("quality gate: FAILED (1 step(s))")


@given(st.lists(st.integers(min_value=0, max_value=2), max_size=8))
def test_format_report__verdict_is_passed_only_when_every_step_passed(
    returncodes: list[int],
) -> None:
    results = [_result(f"step{i}", code) for i, code in enumerate(returncodes)]

    report = format_report(results)

    assert report.endswith("PASSED") == all(code == 0 for code in returncodes)
    assert report.count("[FAIL]") == sum(code != 0 for code in returncodes)


def test_steps_for__fast_tier__is_lint_types_and_plain_tests() -> None:
    assert steps_for(Tier.FAST) == (*LINT_STEPS, FAST_TEST_STEP)


def test_steps_for__pr_tier__swaps_plain_tests_for_coverage_run() -> None:
    steps = steps_for(Tier.PR)

    assert steps == (*LINT_STEPS, COVERAGE_TEST_STEP)
    assert "--cov" in COVERAGE_TEST_STEP.command


def test_parse_tier__defaults_to_fast_and_accepts_pr() -> None:
    assert parse_tier([]) is Tier.FAST
    assert parse_tier(["--tier", "pr"]) is Tier.PR


def _python_step(name: str, code: str) -> CheckStep:
    return CheckStep(name, (sys.executable, "-c", code))


def test_run_step__real_command__captures_exit_status_and_output() -> None:
    passing = run_step(_python_step("ok", "print('hello')"))
    failing = run_step(_python_step("bad", "import sys; print('boom'); sys.exit(3)"))

    assert passing.passed
    assert passing.output == "hello"
    assert failing.returncode == 3
    assert "boom" in failing.output


def test_main__all_steps_pass__exits_zero_and_prints_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check, "steps_for", lambda _tier: (_python_step("ok", "pass"),))

    exit_code = main([])

    assert exit_code == 0
    assert "quality gate: PASSED" in capsys.readouterr().out


def test_main__a_step_fails__exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failing = _python_step("bad", "import sys; sys.exit(1)")
    monkeypatch.setattr(check, "steps_for", lambda _tier: (failing,))

    exit_code = main(["--tier", "pr"])

    assert exit_code == 1
    assert "quality gate: FAILED (1 step(s))" in capsys.readouterr().out
