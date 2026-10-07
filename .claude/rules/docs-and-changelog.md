---
paths:
  - "docs/**/*.md"
  - "changes/**/*.md"
  - "schemas/**"
  - "CHANGELOG.md"
---
# Docs, schemas and change log

- **Every change adds a fragment** in `changes/unreleased/` (`uv run changelog new --type <t> --scope <s> --milestone <M> "<imperative summary>"`). Format and rules: `changes/README.md`. `CHANGELOG.md` and `release-notes/` are generated; never edit them by hand once the generator exists.
- Set impact flags honestly: `schema_version_impact`, `sim_version_impact`, `config_impact`, `migration`, `breaking`. `uv run changelog check` fails otherwise.
- Update design docs in the **same change** as the behaviour they describe. Record deviations from the design in the milestone report (`docs/milestones/Mx.md`), and refresh `docs/status.md` (<= 100 lines) at the end of each milestone.
- JSON Schema in `schemas/` is generated from the Pydantic models (`uv run export-schemas`); never edit it by hand. A drift test fails if it is stale.
- ADRs (`docs/adr/NNNN-title.md`: context / decision / consequences) for non-obvious or hard-to-reverse decisions.
- Agent rules live in `.claude/rules/*.md` (Claude Code) and `.cursor/rules/*.mdc` (Cursor: same body, plus `description`/`globs`/`alwaysApply` frontmatter). When you change a rule, change **both** files in the same commit.
