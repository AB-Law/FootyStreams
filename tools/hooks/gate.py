"""Quality gate run when an AI agent tries to finish its turn (Claude Code and Cursor).

The agent may only stop when the project's fast quality tier (`uv run check`:
ruff, ruff format, mypy, architecture tests, unit/property/contract tests,
changelog check) passes completely. Otherwise the failure report is handed back
to the agent so it keeps working.

Design notes:
  * Standard library only, so it runs before the project environment exists.
  * Does nothing until `pyproject.toml` exists (the design phase has nothing to check).
  * Skips the run when no watched file changed since the last green run.
  * Gives up after `FOOTY_GATE_MAX_RETRIES` consecutive failures (default 8,
    `0` = never give up) so a broken environment cannot loop forever; giving up is
    reported loudly and never counts as a pass.

Environment:
  FOOTY_GATE_COMMAND      command to run (default "uv run check")
  FOOTY_GATE_MAX_RETRIES  consecutive blocked attempts before giving up (default 8)
  FOOTY_GATE_TIMEOUT_S    per-run timeout in seconds (default 840)
  FOOTY_GATE_ROOT         project root override (tests)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COMMAND = "uv run check"
DEFAULT_MAX_RETRIES = 8
DEFAULT_TIMEOUT_S = 840
REPORT_TAIL_LINES = 80
CLAUDE_BLOCK_EXIT_CODE = 2

WATCHED_PATHS = (
    "src",
    "tests",
    "data",
    "schemas",
    "tools",
    "changes",
    "docs",
    "pyproject.toml",
    "uv.lock",
)
IGNORED_DIR_NAMES = frozenset(
    {".git", ".gate", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of one gate run."""

    passed: bool
    report: str


def project_root() -> Path:
    """Return the project root (two levels above this file unless overridden)."""
    override = os.environ.get("FOOTY_GATE_ROOT")
    return Path(override) if override else Path(__file__).resolve().parents[2]


def read_hook_payload() -> dict[str, object]:
    """Parse the JSON the agent passes on stdin; tolerate empty or invalid input."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def watched_files(root: Path) -> list[Path]:
    """List every file whose change should re-trigger the gate, in a stable order."""
    files: list[Path] = []
    for name in WATCHED_PATHS:
        path = root / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(_files_under(path))
    return sorted(files)


def _files_under(directory: Path) -> list[Path]:
    """Recursively collect files, skipping caches and environments."""
    found: list[Path] = []
    for entry in directory.iterdir():
        if entry.name in IGNORED_DIR_NAMES:
            continue
        if entry.is_dir():
            found.extend(_files_under(entry))
        elif entry.is_file():
            found.append(entry)
    return found


def fingerprint(root: Path) -> str:
    """Hash path, size and modification time of all watched files."""
    digest = hashlib.sha256()
    for path in watched_files(root):
        stat = path.stat()
        digest.update(f"{path.relative_to(root)}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def run_gate(root: Path) -> GateResult:
    """Run the quality command and capture a trimmed report on failure."""
    command = shlex.split(os.environ.get("FOOTY_GATE_COMMAND", DEFAULT_COMMAND))
    timeout = int(os.environ.get("FOOTY_GATE_TIMEOUT_S", DEFAULT_TIMEOUT_S))
    try:
        completed = subprocess.run(  # noqa: S603 - command comes from trusted local config
            command, cwd=root, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return GateResult(
            passed=False, report=f"Cannot run the gate: command not found: {command[0]!r}"
        )
    except subprocess.TimeoutExpired:
        return GateResult(passed=False, report=f"The gate timed out after {timeout}s.")
    if completed.returncode == 0:
        return GateResult(passed=True, report="")
    combined = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    return GateResult(passed=False, report="\n".join(combined[-REPORT_TAIL_LINES:]))


def read_counter(state_dir: Path) -> int:
    """Return the number of consecutive blocked attempts recorded so far."""
    try:
        return int((state_dir / "fail_count").read_text())
    except (FileNotFoundError, ValueError):
        return 0


def write_state(state_dir: Path, name: str, value: str) -> None:
    """Persist a small piece of gate state."""
    state_dir.mkdir(exist_ok=True)
    (state_dir / name).write_text(value)


def block_message(report: str, attempt: int, max_retries: int) -> str:
    """Build the instruction handed back to the agent."""
    limit = "unlimited" if max_retries == 0 else str(max_retries)
    return (
        f"QUALITY GATE FAILED (attempt {attempt} of {limit}). Fix every failure below, "
        "then finish. Do not weaken or skip any check.\n\n" + report
    )


def give_up_message(attempts: int) -> str:
    """Build the loud notice shown when the retry cap is reached."""
    return (
        f"QUALITY GATE STILL FAILING after {attempts} attempts. The agent stopped without a "
        "green gate. Run `uv run check` and fix the failures before merging anything."
    )


def respond(agent: str, *, block: bool, message: str = "", notice: str = "") -> int:
    """Emit the agent-specific response and return the process exit code."""
    if agent == "cursor":
        body = {"followup_message": message} if block else {}
        if notice:
            print(notice, file=sys.stderr)
        print(json.dumps(body))
        return 0
    if block:
        print(message, file=sys.stderr)
        return CLAUDE_BLOCK_EXIT_CODE
    if notice:
        print(json.dumps({"systemMessage": notice}))
    return 0


def should_skip(agent: str, payload: dict[str, object], root: Path) -> bool:
    """Return True when there is nothing to gate."""
    if not (root / "pyproject.toml").exists():
        return True
    return agent == "cursor" and payload.get("status", "completed") != "completed"


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("claude", "cursor"), required=True)
    agent = parser.parse_args().agent
    root, payload = project_root(), read_hook_payload()
    if should_skip(agent, payload, root):
        return respond(agent, block=False)

    state_dir = root / ".gate"
    current = fingerprint(root)
    green = state_dir / "last_green"
    if green.exists() and green.read_text() == current:
        return respond(agent, block=False)

    result = run_gate(root)
    if result.passed:
        write_state(state_dir, "last_green", current)
        write_state(state_dir, "fail_count", "0")
        return respond(agent, block=False)

    max_retries = int(os.environ.get("FOOTY_GATE_MAX_RETRIES", DEFAULT_MAX_RETRIES))
    attempt = read_counter(state_dir) + 1
    if max_retries and attempt > max_retries:
        write_state(state_dir, "fail_count", "0")
        return respond(agent, block=False, notice=give_up_message(attempt - 1))
    write_state(state_dir, "fail_count", str(attempt))
    return respond(agent, block=True, message=block_message(result.report, attempt, max_retries))


if __name__ == "__main__":
    sys.exit(main())
