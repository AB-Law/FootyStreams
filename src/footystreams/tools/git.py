"""Small, shared git helpers for the developer tools (no policy, just facts about the repo)."""

from __future__ import annotations

import subprocess
from pathlib import Path

BASE_CANDIDATES = ("origin/main", "main")


class GitError(RuntimeError):
    """A git command failed or the repository is not in a usable state."""


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in `root` without raising on a non-zero exit."""
    return subprocess.run(  # noqa: S603 - fixed git subcommands, no shell
        ["git", *arguments],  # noqa: S607 - git is resolved from PATH on purpose
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def git_output(root: Path, *arguments: str) -> str:
    """Run a git command and return stdout, raising `GitError` if it fails."""
    completed = run_git(root, *arguments)
    if completed.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def resolve_base(root: Path, requested: str | None = None) -> str:
    """Return the ref to compare against: the requested one, else origin/main, else main."""
    candidates = [requested] if requested else list(BASE_CANDIDATES)
    for candidate in candidates:
        if run_git(root, "rev-parse", "--verify", "--quiet", str(candidate)).returncode == 0:
            return str(candidate)
    raise GitError(f"none of {candidates} exists in this repository")


def merge_base(root: Path, base: str) -> str:
    """The commit where the current branch left `base`."""
    return git_output(root, "merge-base", base, "HEAD").strip()
