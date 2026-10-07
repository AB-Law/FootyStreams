## Summary
<!-- What changes and why, in 2-4 bullets. Link the design section (e.g. docs/design/02-simulation.md section 6). -->
-

## Changes
<!-- One short subsection per slice of the milestone commit plan (docs/design/06-milestones.md); the reviewer reads commit by commit. -->
-

## How verified
<!-- Commands you ran and their results. Paste key output. -->
- [ ] `uv run check` (all green)
- [ ] Extra: <!-- e.g. `uv run check --tier pr`, `uv run sim --home KES --away HAR --seed 7` output, benchmark numbers -->

## Impact
- `SIM_VERSION` impact: none / patch / minor / major <!-- same seed gives different output? -->
- `SCHEMA_VERSION` impact: none / patch / minor / major
- Config / YAML keys changed: no / yes (<!-- which -->)
- Migration needed: no / yes
- Performance: <!-- budget unaffected, or before/after numbers + benchmark id -->

## Docs and changelog
- Changelog fragment: `changes/unreleased/____-____.md`
- Design docs updated: <!-- files, or "none needed" -->

## Follow-ups
<!-- Deliberately out of scope here; link issues/fragments. -->

## Checklist (docs/design/11-engineering-standards.md section 10)
- [ ] Each function/class has one clear job; no magic numbers or flag arguments; complexity and size limits respected
- [ ] No duplicated logic; no abstraction without a second user or a seam
- [ ] Layering respected; pure core stays pure; randomness only via passed `SimRng`
- [ ] Tests at the right levels; invariants via `verify/`, not re-implemented
- [ ] Atomic commits (<= 400 changed lines each, generated files excluded); the PR reads well commit by commit
