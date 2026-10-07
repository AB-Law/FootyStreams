---
id: 0007
date: 2026-10-07
type: build
scope: [tools, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the uv project, strict lint/type/test configuration and the 'uv run check' quality gate.
---
First M0 slice. Python 3.12 src-layout package `footystreams` (hatchling), ruff with the clean-code limits from
`docs/design/11-engineering-standards.md` (complexity 8, 5 args, docstrings, magic numbers, flag arguments), mypy
strict over `src`, `tests` and `tools`, pytest. `uv run check` runs ruff lint, ruff format, mypy, the fast pytest tier
executing all steps and reporting every failure; the end-of-turn Stop hook now runs it
for real. Existing tooling (`tools/hooks/gate.py`, `tools/rules_sync.py`) was brought in line with the lint rules.
Follow-ups in later M0 slices: architecture tests, factories, changelog tool, CI, PR-size/commit-msg checks.
