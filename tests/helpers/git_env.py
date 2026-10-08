"""Keep tests away from the repository that happens to be running them.

Git exports the location of its repository (``GIT_DIR``, ``GIT_INDEX_FILE``, ``GIT_WORK_TREE``...)
to hooks, and in a linked worktree it always does. A test that runs ``git init`` and
``git commit`` in a temporary directory then acts on the *real* repository instead: the pre-commit
gate once committed a junk "initial" commit onto a branch, flipped ``core.bare`` and wrote a test
identity into the shared config. Every test therefore starts with these variables removed.
"""

from __future__ import annotations

import pytest

REPOSITORY_LOCATION_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
)


def scrub_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the variables that tell git which repository to use (restored after the test)."""
    for name in REPOSITORY_LOCATION_VARIABLES:
        monkeypatch.delenv(name, raising=False)
