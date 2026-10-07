# ADR 0004: Change fragments as the change log, and a gate every agent turn must pass

Status: accepted (2026-10-07). Design reference: `docs/design/11-engineering-standards.md` sections 7, 11, 12.

## Context
Work is done by humans and AI agents. The change history must be readable by people (release notes) and by
tools and agents (context), merge without conflicts, and stay honest about breaking changes and version
impact. Agents must not finish a turn with a red build.

## Decision
- One small markdown fragment per change in `changes/unreleased/` with validated frontmatter (type, scope,
  milestone, breaking, schema and simulation version impact, migration). `CHANGELOG.md` and
  `release-notes/vX.Y.Z.{md,json}` are generated from fragments; `uv run changelog check` and
  `build --check` are part of the quality gate.
- `uv run check` (lint, format, strict types, change-log checks, tests) is the quality gate. A Stop hook runs it
  at the end of every agent turn (`tools/hooks/gate.py`, wired for Claude Code and Cursor) and blocks until it
  passes, giving up loudly after a retry cap so a broken environment cannot loop forever.
- Git workflow: short-lived branches, atomic Conventional Commits (checked by a commit-msg hook), small PRs
  (target 400 changed lines, hard cap 800), and a human review before anything is pushed or a PR opened.

## Consequences
- Every change carries a fragment, and the check fails otherwise (golden or schema changes also need the matching
  impact flag).
- Not yet enforced: that the `SIM_VERSION` / `SCHEMA_VERSION` constants were actually bumped; those constants
  arrive with the simulation and schemas.
- The Stop hook and pre-commit hook add a few seconds per turn or commit; the fast tier has a 60 second budget.
