"""Measure how big a pull request is, ignoring generated files: `uv run pr-size`.

Target <= 400 changed lines, hard cap 800 (docs/design/11-engineering-standards.md section 12).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from footystreams.tools.git import GitError, git_output, merge_base, resolve_base
from footystreams.tools.paths import PROJECT_ROOT

TARGET_LINES = 400
HARD_CAP_LINES = 800
# Generated or bulk files that do not make a PR harder to review.
EXCLUDED_PREFIXES = (
    "uv.lock",
    "schemas/",
    "tests/golden/",
    "data/worlds/",
    "release-notes/",
    "CHANGELOG.md",
    "changes/released/",
)


class Verdict(StrEnum):
    """How a PR size compares with the target and the cap."""

    OK = "ok"
    OVER_TARGET = "over target"
    OVER_CAP = "OVER THE HARD CAP"


def counted_lines(numstat: str) -> int:
    """Sum added + deleted lines from `git diff --numstat` output, skipping excluded files."""
    total = 0
    for line in numstat.splitlines():
        added, _, rest = line.partition("\t")
        deleted, _, path = rest.partition("\t")
        if path.startswith(EXCLUDED_PREFIXES) or not (added.isdigit() and deleted.isdigit()):
            continue  # excluded file, or a binary file (git prints '-')
        total += int(added) + int(deleted)
    return total


def verdict_for(lines: int) -> Verdict:
    """Compare a size with the target and the hard cap."""
    if lines > HARD_CAP_LINES:
        return Verdict.OVER_CAP
    return Verdict.OVER_TARGET if lines > TARGET_LINES else Verdict.OK


def main(argv: Sequence[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    """Print the PR size; exit 1 only when over the hard cap (unless --allow-large)."""
    parser = argparse.ArgumentParser(prog="pr-size", description=__doc__)
    parser.add_argument("--base", default=None, help="ref the PR targets (default: origin/main)")
    parser.add_argument("--allow-large", action="store_true", help="a human approved a large PR")
    arguments = parser.parse_args(argv)
    try:
        base = resolve_base(root, arguments.base)
        numstat = git_output(root, "diff", "--numstat", merge_base(root, base), "HEAD")
    except GitError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    lines = counted_lines(numstat)
    verdict = verdict_for(lines)
    print(f"PR size: {lines} changed lines (generated files excluded): {verdict}")
    return 1 if verdict is Verdict.OVER_CAP and not arguments.allow_large else 0


if __name__ == "__main__":
    sys.exit(main())
