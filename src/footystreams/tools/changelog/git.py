"""Which files did this branch change? The only git question the change log asks."""

from __future__ import annotations

from pathlib import Path

from footystreams.tools.changelog.policy import ChangedFile
from footystreams.tools.git import git_output, merge_base


def changed_files(root: Path, base: str) -> list[ChangedFile]:
    """Files changed since the merge-base with `base`, including uncommitted and untracked ones."""
    tracked = git_output(root, "diff", "--name-status", "--no-renames", merge_base(root, base))
    untracked = git_output(root, "ls-files", "--others", "--exclude-standard")
    found = [_parse_status_line(line) for line in tracked.splitlines() if line.strip()]
    found.extend(ChangedFile(path, "A") for path in untracked.splitlines() if path.strip())
    return found


def _parse_status_line(line: str) -> ChangedFile:
    status, _, path = line.partition("\t")
    return ChangedFile(path.strip(), status[:1])
