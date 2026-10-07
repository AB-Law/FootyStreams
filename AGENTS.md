# AGENTS.md — entry point for AI agents (Claude Code, Cursor, others) and humans

**FootyStreams**: a fictional football league that runs as a 24/7 live broadcast — deterministic match simulation, typed event stream, living league world, and a long-running engine (`uv run engine`). LLM commentary, TTS and rendering are future layers behind clean seams. A failure here is visible on air.

## Where things are
| What | Where |
|------|-------|
| Design (index, schemas, sim, events, architecture, testing, standards, runtime, voice) | `docs/design/README.md` |
| **Rules for agents** (same content for both tools) | Claude Code: `.claude/rules/*.md`; Cursor: `.cursor/rules/*.mdc` |
| Current state / next steps (from Phase 2) | `docs/status.md` |
| Change log (fragments → generated `CHANGELOG.md`, release notes) | `changes/` |
| Milestone reports and ADRs | `docs/milestones/`, `docs/adr/` |

## The rules, in one breath
Read `docs/status.md` first. Keep the core deterministic and pure; check invariants only via `verify/`; write clean, small, SOLID, DRY code (limits are lint-enforced); measure before optimising; add tests and a changelog fragment for every change; update the design docs in the same change; **never weaken a gate**. Details: `.claude/rules/core.md`, `clean-code.md`, `architecture.md`, `sim.md`, `testing.md`, `docs-and-changelog.md`, `git-workflow.md`.

## Workflow (summary of `.claude/rules/git-workflow.md`)
Branch from `main` before editing → small atomic Conventional Commits (local) → gate green → **stop for the user's review** → only after their explicit go-ahead, push and open a small PR (≤ 400 changed lines, ≤ 800 hard cap) with a clear description → rebase-and-merge after review. **No push and no PR without the human review checkpoint.** Never commit to `main`; never merge, force-push shared branches, or skip hooks unless the user says so. Remote: `https://github.com/AB-Law/FootyStreams` (public, currently empty).

## Definition of done: the quality gate
`uv run check` (ruff, ruff format, mypy strict, architecture, unit/property/contract tests and changelog checks) must pass **completely**. A **Stop hook** (`tools/hooks/gate.py`, wired in `.claude/settings.json` and `.cursor/hooks.json`) runs it at the end of every turn and hands failures back to the agent until it is green (it skips when nothing changed since the last green run, and gives up loudly after `FOOTY_GATE_MAX_RETRIES`, default 8, to avoid infinite loops). Before M0 there is no `pyproject.toml`, so the gate is a no-op.

## Editing the rules
Change `.claude/rules/<name>.md` and `.cursor/rules/<name>.mdc` together in the same commit (same body; Cursor adds `description`/`globs`/`alwaysApply` frontmatter). Cursor also reads this file natively.
