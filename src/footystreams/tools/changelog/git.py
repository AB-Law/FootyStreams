"""The little git access the change log needs: which files did this branch change?"""

from __future__ import annotations

import subprocess
from pathlib import Path

from footystreams.tools.changelog.policy import ChangedFile

BASE_CANDIDATES = ("origin/main", "main")


class GitError(RuntimeError):
    """A git command failed or the repository is not in a usable state."""


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed git subcommands, no shell
        ["git", *arguments],  # noqa: S607 - git is resolved from PATH on purpose
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(root: Path, *arguments: str) -> str:
    completed = _run(root, *arguments)
    if completed.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def resolve_base(root: Path, requested: str | None = None) -> str:
    """Return the ref to compare against: the requested one, else origin/main, else main."""
    candidates = [requested] if requested else list(BASE_CANDIDATES)
    for candidate in candidates:
        if _run(root, "rev-parse", "--verify", "--quiet", str(candidate)).returncode == 0:
            return str(candidate)
    raise GitError(f"none of {candidates} exists in this repository")


def changed_files(root: Path, base: str) -> list[ChangedFile]:
    """Files changed since the merge-base with `base`, including uncommitted and untracked ones."""
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    tracked = _git(root, "diff", "--name-status", "--no-renames", merge_base)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    found = [_parse_status_line(line) for line in tracked.splitlines() if line.strip()]
    found.extend(ChangedFile(path, "A") for path in untracked.splitlines() if path.strip())
    return found


def _parse_status_line(line: str) -> ChangedFile:
    status, _, path = line.partition("\t")
    return ChangedFile(path.strip(), status[:1])
