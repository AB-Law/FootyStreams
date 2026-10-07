"""Check that a commit message follows Conventional Commits: `type(scope): imperative summary`.

Used by the `commit-msg` git hook (`uv run commit-msg-check <message-file>`).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

TYPES = (
    "feat",
    "fix",
    "refactor",
    "perf",
    "test",
    "docs",
    "build",
    "ci",
    "chore",
    "style",
    "revert",
)
MAX_SUBJECT_LENGTH = 72
SUBJECT = re.compile(rf"^({'|'.join(TYPES)})(\([a-z0-9][a-z0-9-]*\))?!?: \S")
# Messages git or the autosquash workflow generate; they are fixed up before review.
GENERATED_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ")


def problems_with(message: str) -> list[str]:
    """List what is wrong with a commit message (empty when it is fine)."""
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    if not any(line.strip() for line in lines):
        return ["the commit message is empty"]
    subject = next(line for line in lines if line.strip())
    if subject.startswith(GENERATED_PREFIXES):
        return []
    found = []
    if not SUBJECT.match(subject):
        found.append(
            f"subject must look like 'type(scope): summary' with type in {', '.join(TYPES)}"
        )
    if len(subject) > MAX_SUBJECT_LENGTH:
        found.append(f"subject is {len(subject)} characters; the limit is {MAX_SUBJECT_LENGTH}")
    if len(lines) > 1 and lines[1].strip():
        found.append("leave a blank line between the subject and the body")
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """Check the message in the file named by the first argument."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: commit-msg-check <message-file>", file=sys.stderr)
        return 2
    problems = problems_with(Path(arguments[0]).read_text(encoding="utf-8"))
    for problem in problems:
        print(f"commit message: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
