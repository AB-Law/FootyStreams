---
id: 0008
date: 2026-10-07
type: removed
scope: [tools, design]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Remove the Cursor rules generator; keep plain, hand-maintained .cursor/rules copies.
---
`tools/rules_sync.py` and its `--check` step in the quality gate are removed (less machinery to maintain). The
`.cursor/rules/*.mdc` files stay as ordinary files with Cursor frontmatter and the same body as the matching
`.claude/rules/*.md`; the generated-file banner was dropped. Rule changes now touch both files in the same commit.
Docs, `AGENTS.md` and the milestone plan were updated; earlier fragments (0004, 0006) are left as historical record.
