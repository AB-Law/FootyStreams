"""Generate Cursor rules from the Claude Code rules, which are the single source of truth.

Source: `.claude/rules/<name>.md` - plain markdown, optionally with frontmatter

    ---
    paths:
      - "src/**/*.py"
    ---

Rules without `paths` apply to every session. The first `# ` heading is the rule's title.

Output: `.cursor/rules/<name>.mdc` with `description`, `globs` and `alwaysApply`.

Usage:
  python tools/rules_sync.py          write the Cursor files
  python tools/rules_sync.py --check  exit 1 if any Cursor file is stale or orphaned
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".claude" / "rules"
CURSOR_DIR = ROOT / ".cursor" / "rules"
FRONTMATTER_FENCE = "---"
TITLE_PREFIX = "# "


@dataclass(frozen=True)
class Rule:
    """One rule parsed from a Claude rule file."""

    name: str
    title: str
    paths: tuple[str, ...]
    body: str

    @property
    def always_applies(self) -> bool:
        """Rules without path scopes apply to every session."""
        return not self.paths


def parse_rule(path: Path) -> Rule:
    """Parse a Claude rule file into its path scopes, title and body."""
    lines = path.read_text(encoding="utf-8").splitlines()
    paths: list[str] = []
    if lines and lines[0] == FRONTMATTER_FENCE:
        end = lines.index(FRONTMATTER_FENCE, 1)
        paths = _parse_paths(lines[1:end])
        lines = lines[end + 1 :]
    title = next(
        (line.removeprefix(TITLE_PREFIX) for line in lines if line.startswith(TITLE_PREFIX)), ""
    )
    if not title:
        raise ValueError(f"{path}: rule needs a '# Title' heading")
    return Rule(path.stem, title.strip(), tuple(paths), "\n".join(lines).strip("\n"))


def _parse_paths(frontmatter_lines: list[str]) -> list[str]:
    """Extract the `paths:` list items from frontmatter lines."""
    return [
        line.strip().removeprefix("- ").strip().strip('"')
        for line in frontmatter_lines
        if line.strip().startswith("- ")
    ]


def render_cursor(rule: Rule) -> str:
    """Render the Cursor `.mdc` file for a rule."""
    fields = [f"description: {rule.title}"]
    if rule.paths:
        fields.append(f"globs: {', '.join(rule.paths)}")
    fields.append(f"alwaysApply: {str(rule.always_applies).lower()}")
    header = "\n".join([FRONTMATTER_FENCE, *fields, FRONTMATTER_FENCE])
    source = f".claude/rules/{rule.name}.md"
    notice = f"<!-- GENERATED from {source} by tools/rules_sync.py - edit the source. -->"
    return f"{header}\n{notice}\n{rule.body}\n"


def expected_outputs() -> dict[Path, str]:
    """Map every Cursor file path to its expected content."""
    return {
        CURSOR_DIR / f"{rule.name}.mdc": render_cursor(rule)
        for rule in (parse_rule(source) for source in sorted(SOURCE_DIR.glob("*.md")))
    }


def stale_files(outputs: dict[Path, str]) -> list[Path]:
    """Return Cursor files that are missing, differ from expectation, or have no source."""
    stale = [
        path
        for path, content in outputs.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    orphans = [path for path in sorted(CURSOR_DIR.glob("*.mdc")) if path not in outputs]
    return stale + orphans


def write_outputs(outputs: dict[Path, str]) -> None:
    """Write all Cursor files and remove orphans."""
    CURSOR_DIR.mkdir(parents=True, exist_ok=True)
    for orphan in (path for path in CURSOR_DIR.glob("*.mdc") if path not in outputs):
        orphan.unlink()
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if Cursor files are stale")
    check_only = parser.parse_args().check
    outputs = expected_outputs()
    if check_only:
        stale = stale_files(outputs)
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    write_outputs(outputs)
    print(f"wrote {len(outputs)} Cursor rule files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
