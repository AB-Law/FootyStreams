# Change fragments

Every change to the project adds **one small file** here (`changes/unreleased/NNNN-slug.md`). Fragments are the single source of truth for the change log: `uv run changelog build` compiles `CHANGELOG.md`, and `uv run changelog release X.Y.Z` produces `release-notes/vX.Y.Z.md` (human) and `.json` (machine). They are written to be read by people, Cursor and Claude alike. Full rules: `docs/design/11-engineering-standards.md` §7.

Create one with `uv run changelog new --type added --scope sim --milestone M5 "Add offside detection"` (available from M0; until then copy an existing fragment).

## Format

```markdown
---
id: 0007                     # zero-padded, unique, increasing
date: 2026-10-07             # real calendar date of the change
type: added                  # added | changed | fixed | removed | deprecated | security | perf | refactor | test | docs | build
scope: [sim, events]         # domain | events | sim | league | persistence | seed | cli | tools | schemas | data | docs | ci | design
milestone: M5               # M0..M14, or "design" during Phase 1
breaking: false
schema_version_impact: none  # none | patch | minor | major  (JSON Schema of events/models)
sim_version_impact: none     # none | patch | minor | major  (match output for the same seed changes => not none)
config_impact: false         # SimConfig / YAML keys added, changed or removed
migration: false             # needs an Alembic or data migration
summary: One imperative, user-facing line.
---
Optional detail: what and why, how it was verified (tests/benchmarks), links to design sections,
follow-ups, migration notes.
```

## Rules checked by `uv run changelog check` (pre-commit and CI)

- Changed files under `src/`, `data/`, `schemas/` need a fragment.
- Changed golden digests need `sim_version_impact` ≠ `none` and a bumped `SIM_VERSION`.
- Changed `schemas/` need `schema_version_impact` ≠ `none` and a bumped `SCHEMA_VERSION`.
- Fragments must parse and use only the allowed values.
