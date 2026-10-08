"""A git hook's repository variables must not steer a test's temporary repository.

Seen in a linked worktree: the pre-commit gate ran the suite with ``GIT_DIR`` and friends exported,
and the tests that make a throwaway repository (``git init``, ``git commit``) wrote into the real
one instead: a junk commit on the branch being committed to, ``core.bare = true`` and a test
identity in the shared config. This reproduces the situation with a decoy repository.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.helpers.git_env import REPOSITORY_LOCATION_VARIABLES, scrub_git_environment


def _git(directory: Path, *arguments: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed argv, a throwaway directory
        ["git", *arguments],  # noqa: S607
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    return result.stdout.strip()


def _decoy(path: Path) -> Path:
    path.mkdir()
    clean = {k: v for k, v in os.environ.items() if k not in REPOSITORY_LOCATION_VARIABLES}
    for arguments in (
        ["init", "-b", "main"],
        ["config", "user.email", "real@example.com"],
        ["config", "user.name", "Real"],
        ["commit", "--allow-empty", "-m", "the real history"],
    ):
        subprocess.run(["git", *arguments], cwd=path, check=True, capture_output=True, env=clean)  # noqa: S603, S607
    return path


def test_scrub__removes_every_repository_location_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in REPOSITORY_LOCATION_VARIABLES:
        monkeypatch.setenv(name, str(tmp_path))

    scrub_git_environment(monkeypatch)

    assert not [name for name in REPOSITORY_LOCATION_VARIABLES if name in os.environ]


def test_a_throwaway_repository__does_not_write_into_the_one_the_hook_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decoy = _decoy(tmp_path / "decoy")
    history_before = _git(decoy, "log", "--oneline")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    monkeypatch.setenv("GIT_INDEX_FILE", str(decoy / ".git" / "index"))
    scrub_git_environment(monkeypatch)  # what the autouse fixture does before every test

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    for arguments in (
        ["init", "-b", "main"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
        ["commit", "--allow-empty", "-m", "initial"],
    ):
        _git(scratch, *arguments)

    assert _git(decoy, "log", "--oneline") == history_before
    assert _git(decoy, "config", "user.name") == "Real"
    assert _git(decoy, "config", "core.bare") == "false"
    assert _git(scratch, "log", "--oneline").endswith("initial")
