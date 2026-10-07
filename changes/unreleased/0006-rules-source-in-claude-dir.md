---
id: 0006
date: 2026-10-07
type: changed
scope: [design, tools]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Make .claude/rules the source of agent rules and generate .cursor/rules from it; remove docs/rules.
---
The rules now live where the tools read them. `.claude/rules/*.md` (path-scoped via `paths:` frontmatter, always-on
when absent) are hand-edited; `tools/rules_sync.py` generates `.cursor/rules/*.mdc` (description from the title,
`globs`, `alwaysApply`) and `--check` fails on stale or orphaned Cursor files. `docs/rules/` was removed and all
references updated.
