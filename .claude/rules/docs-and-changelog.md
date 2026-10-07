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
- `.claude/rules/*.md` are the **source** of the agent rules (read by Claude Code, and by Cursor via `AGENTS.md`); `.cursor/rules/*.mdc` are **generated** from them by `uv run rules sync` (`--check` is part of `uv run check`). Edit the `.claude/rules` file, never the `.mdc`.
