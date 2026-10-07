"""Run the project's quality gate: `uv run check`.

The fast tier (T0, see docs/design/10-testing-strategy.md) runs on every commit and at the
end of every agent turn. Every step runs even if an earlier one fails, so a single run shows
all problems at once. The process exits non-zero if any step fails.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FAILURE_OUTPUT_TAIL_LINES = 60
PYTHON = sys.executable


@dataclass(frozen=True)
class CheckStep:
    """One named command in the quality gate."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class StepResult:
    """Outcome of running one step."""

    step: CheckStep
    returncode: int
    seconds: float
    output: str

    @property
    def passed(self) -> bool:
        """True when the command exited with status 0."""
        return self.returncode == 0


StepRunner = Callable[[CheckStep], StepResult]

FAST_STEPS: tuple[CheckStep, ...] = (
    CheckStep("ruff lint", (PYTHON, "-m", "ruff", "check", ".")),
    CheckStep("ruff format", (PYTHON, "-m", "ruff", "format", "--check", ".")),
    CheckStep("mypy --strict", (PYTHON, "-m", "mypy")),
    CheckStep("pytest (fast tier)", (PYTHON, "-m", "pytest", "-m", "not slow", "-q")),
)


def run_step(step: CheckStep) -> StepResult:
    """Run one step in the project root and capture its output."""
    started = time.perf_counter()
    completed = subprocess.run(  # noqa: S603 - commands are fixed constants above
        step.command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    elapsed = time.perf_counter() - started
    output = (completed.stdout + completed.stderr).strip()
    return StepResult(step, completed.returncode, elapsed, output)


def run_steps(steps: Sequence[CheckStep], runner: StepRunner = run_step) -> list[StepResult]:
    """Run every step, in order, regardless of earlier failures."""
    return [runner(step) for step in steps]


def format_report(results: Sequence[StepResult]) -> str:
    """Build the human-readable summary, with output only for failing steps."""
    lines = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.step.name} ({result.seconds:.1f}s)")
        if not result.passed:
            tail = result.output.splitlines()[-FAILURE_OUTPUT_TAIL_LINES:]
            lines.extend(f"    {line}" for line in tail)
    failed = sum(not result.passed for result in results)
    lines.append("quality gate: " + ("PASSED" if failed == 0 else f"FAILED ({failed} step(s))"))
    return "\n".join(lines)


def main() -> int:
    """Run the fast tier and return the process exit code."""
    results = run_steps(FAST_STEPS)
    print(format_report(results))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
