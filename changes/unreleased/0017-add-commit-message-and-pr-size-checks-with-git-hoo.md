---
id: 0017
date: 2026-10-07
type: added
scope: [tools, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add commit message and PR size checks with git hooks
---
'uv run commit-msg-check' enforces Conventional Commits (type(scope): summary, 72 characters, blank line before the body; merge/fixup messages allowed). 'uv run pr-size' counts added+deleted lines against the PR base, ignoring generated files (lockfile, schemas, goldens, worlds, release notes): target 400, hard cap 800, --allow-large for a human-approved exception. .githooks/pre-commit runs 'uv run check'; .githooks/commit-msg runs the message check. Enable once per clone with 'git config core.hooksPath .githooks'. Shared git helpers moved to footystreams.tools.git.
