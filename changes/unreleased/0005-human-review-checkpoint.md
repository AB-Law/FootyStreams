---
id: 0005
date: 2026-10-07
type: changed
scope: [design, ci]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Require a human review checkpoint before any push or pull request; record the GitHub remote.
---
Agents commit atomically on local branches and stop to present a review package (branch, log, diff stat, what/why,
verification, impact flags). A push or `gh pr create` happens only after the owner's explicit go-ahead; approvals do
not carry over between slices. The same applies to the first push to the empty remote
(`https://github.com/AB-Law/FootyStreams`, public). Updated `.claude/rules/git-workflow.md` (and the generated Cursor
rule file), `AGENTS.md`, `11-engineering-standards.md` section 12, `06-milestones.md` (M0, quality gate item 7) and
`09-schema-decisions.md` (L31, L32; O6 resolved).
