import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *arguments: str) -> None:
    """Run a git command in `repo`, failing the test if git fails."""
    subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway git repository on a `feature` branch that starts level with `main`."""
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    git(tmp_path, "switch", "-c", "feature")
    return tmp_path
