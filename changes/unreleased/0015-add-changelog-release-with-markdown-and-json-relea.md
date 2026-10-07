---
id: 0015
date: 2026-10-07
type: added
scope: [tools]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add 'changelog release' with Markdown and JSON release notes
---
'uv run changelog release X.Y.Z' moves the unreleased fragments to changes/released/X.Y.Z/, writes release-notes/vX.Y.Z.md (breaking changes, migration steps, strongest sim/schema version impact, grouped changes) and .json (structured, for machines, e.g. a future patch-notes segment), and regenerates CHANGELOG.md with a section per release. Versions are ordered numerically.
