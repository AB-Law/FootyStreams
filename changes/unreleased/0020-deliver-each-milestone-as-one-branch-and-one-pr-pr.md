---
id: 0020
date: 2026-10-07
type: changed
scope: [design, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Deliver each milestone as one branch and one PR; PR size becomes informational
---
Replaces the per-slice, stacked-PR workflow used for M0 (13 PRs) with one branch and one PR per milestone. The milestone's slice list is now the commit plan: atomic Conventional Commits of at most 400 changed lines each, reviewed commit by commit, with a PR description that has one section per slice. The human review checkpoint moves to the end of the milestone (interim looks at the local branch are previews, not approval to push). Updated the git workflow rule pair (.claude and .cursor), AGENTS.md, design 06 and 11 section 12, the PR template, and the CI pr-size job, which now only reports.
