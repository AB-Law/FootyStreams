"""Command line for the change log: `uv run changelog <command>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from footystreams.tools import git as repo_git
from footystreams.tools.changelog import git
from footystreams.tools.changelog.build import render_changelog
from footystreams.tools.changelog.fragment import (
    SCOPES,
    ChangeType,
    Fragment,
    FragmentError,
    Impact,
    parse_fragment,
)
from footystreams.tools.changelog.policy import check_change, is_fragment_path
from footystreams.tools.changelog.release import write_release_notes
from footystreams.tools.changelog.store import FragmentStore
from footystreams.tools.paths import PROJECT_ROOT

CHANGELOG_FILE = "CHANGELOG.md"


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with one sub-command per action."""
    parser = argparse.ArgumentParser(prog="changelog", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    _add_new(commands.add_parser("new", help="create the next change fragment"))
    check = commands.add_parser("check", help="check this change has the fragments it needs")
    check.add_argument("--base", default=None, help="ref to compare with (default: origin/main)")
    build = commands.add_parser("build", help="write CHANGELOG.md from the fragments")
    build.add_argument("--check", action="store_true", help="fail if CHANGELOG.md is stale")
    release = commands.add_parser("release", help="publish the unreleased fragments as a version")
    release.add_argument("version", help="MAJOR.MINOR.PATCH")
    release.add_argument("--date", type=date.fromisoformat, default=None, help="default: today")
    return parser


def _add_new(new: argparse.ArgumentParser) -> None:
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


def main(argv: Sequence[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    """Run the requested command and return the process exit code."""
    arguments = build_parser().parse_args(argv)
    store = FragmentStore(root / "changes")
    try:
        if arguments.command == "new":
            return _new(arguments, store)
        if arguments.command == "check":
            return _check(arguments, root)
        if arguments.command == "release":
            return _release(arguments, store, root)
        return _build(arguments, store, root / CHANGELOG_FILE)
    except (FragmentError, repo_git.GitError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _new(arguments: argparse.Namespace, store: FragmentStore) -> int:
    print(store.add(_fragment_from(arguments, store.next_id())))
    return 0


def _check(arguments: argparse.Namespace, root: Path) -> int:
    changed = git.changed_files(root, repo_git.resolve_base(root, arguments.base))
    fragments = [
        parse_fragment((root / item.path).read_text(encoding="utf-8"), item.path)
        for item in changed
        if item.status != "D" and is_fragment_path(item.path)
    ]
    problems = check_change(changed, fragments)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def _build(arguments: argparse.Namespace, store: FragmentStore, target: Path) -> int:
    text = render_changelog(store.unreleased(), store.releases())
    if arguments.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == text:
            return 0
        print(f"{target.name} is stale: run 'uv run changelog build'", file=sys.stderr)
        return 1
    target.write_text(text, encoding="utf-8", newline="\n")
    return 0


def _release(arguments: argparse.Namespace, store: FragmentStore, root: Path) -> int:
    release = store.publish(arguments.version, arguments.date or date.today())
    notes = write_release_notes(root, release)
    changelog = render_changelog(store.unreleased(), store.releases())
    (root / CHANGELOG_FILE).write_text(changelog, encoding="utf-8", newline="\n")
    for path in notes:
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
