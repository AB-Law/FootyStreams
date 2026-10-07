from footystreams.tools.check import (
    FAST_STEPS,
    CheckStep,
    StepResult,
    format_report,
    run_steps,
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


def test_fast_steps__cover_lint_format_types_and_tests() -> None:
    names = {step.name for step in FAST_STEPS}

    assert names == {
        "ruff lint",
        "ruff format",
        "mypy --strict",
        "pytest (fast tier)",
    }
