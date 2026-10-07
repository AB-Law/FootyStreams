"""Command line for the change log: `uv run changelog <command>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from footystreams.tools.changelog.fragment import (
    SCOPES,
    ChangeType,
    Fragment,
    FragmentError,
    Impact,
    parse_fragment,
)
from footystreams.tools.changelog.store import FragmentStore
from footystreams.tools.paths import CHANGES_DIR


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with one sub-command per action."""
    parser = argparse.ArgumentParser(prog="changelog", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="create the next change fragment")
    new.add_argument("summary", help="one imperative, user-facing line")
    new.add_argument("--type", required=True, choices=[kind.value for kind in ChangeType])
    new.add_argument("--scope", required=True, nargs="+", choices=sorted(SCOPES))
    new.add_argument("--milestone", required=True, help="M0..M14 or 'design'")
    new.add_argument("--schema-impact", choices=[i.value for i in Impact], default="none")
    new.add_argument("--sim-impact", choices=[i.value for i in Impact], default="none")
    new.add_argument("--breaking", action="store_true")
    new.add_argument("--config-impact", action="store_true")
    new.add_argument("--migration", action="store_true")
    new.add_argument("--body", default="", help="optional longer explanation")
    new.add_argument("--date", type=date.fromisoformat, default=None, help="default: today")
    return parser


def main(argv: Sequence[str] | None = None, changes_dir: Path = CHANGES_DIR) -> int:
    """Run the requested command and return the process exit code."""
    arguments = build_parser().parse_args(argv)
    store = FragmentStore(changes_dir)
    try:
        return _create_fragment(arguments, store)
    except FragmentError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _create_fragment(arguments: argparse.Namespace, store: FragmentStore) -> int:
    candidate = _fragment_from(arguments, store.next_id())
    path = store.add(candidate)
    print(path)
    return 0


def _fragment_from(arguments: argparse.Namespace, fragment_id: str) -> Fragment:
    """Build a validated fragment from CLI arguments (validation reuses the file parser)."""
    metadata = "\n".join(
        [
            "---",
            f"id: {fragment_id}",
            f"date: {(arguments.date or date.today()).isoformat()}",
            f"type: {arguments.type}",
            f"scope: [{', '.join(arguments.scope)}]",
            f"milestone: {arguments.milestone}",
            f"breaking: {str(arguments.breaking).lower()}",
            f"schema_version_impact: {arguments.schema_impact}",
            f"sim_version_impact: {arguments.sim_impact}",
            f"config_impact: {str(arguments.config_impact).lower()}",
            f"migration: {str(arguments.migration).lower()}",
            f"summary: {_quoted(arguments.summary)}",
            "---",
            arguments.body,
        ]
    )
    return parse_fragment(metadata, source="<command line>")


def _quoted(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


if __name__ == "__main__":
    sys.exit(main())
