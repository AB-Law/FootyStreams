---
id: 0014
date: 2026-10-07
type: added
scope: [tools]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add 'changelog check' and 'changelog build' and enforce them in the quality gate
---
'check' fails when code changes without a fragment, or when golden files or schemas change without the matching version-impact flag (it compares against origin/main, else main, and includes uncommitted and untracked files). 'build' writes CHANGELOG.md from the fragments, replacing the hand-written file; 'build --check' fails when it is stale. Both run in 'uv run check'. Not yet enforced: that SIM_VERSION and SCHEMA_VERSION constants were actually bumped (they do not exist yet).
