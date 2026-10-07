---
id: 0009
date: 2026-10-07
type: build
scope: [tools]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Replace .gitignore with a complete Python, tooling and project ruleset.
---
Covers Python build output, virtualenvs, tool caches and coverage, secrets, local agent/IDE state (keeping
`.claude/rules`, `.claude/settings.json`, `.cursor/rules` and `.cursor/hooks.json` tracked), OS files, databases,
engine state and logs, generated worlds other than `data/worlds/default/`, and future audio output. Patterns were
checked with `git check-ignore`.
