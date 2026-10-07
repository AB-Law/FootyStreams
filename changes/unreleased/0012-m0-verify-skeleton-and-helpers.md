---
id: 0012
date: 2026-10-07
type: added
scope: [verify, tools]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the verify package's Violation type and the shared test helpers and factories packages.
---
`footystreams.verify.Violation` (code, message, optional subject; sortable) and `format_violations` are the one result
type for every invariant check (catalogue in `docs/design/10-testing-strategy.md` section 9). `tests/helpers` holds
shared assertions that delegate to `verify`, and `tests/factories` establishes where model builders will live
(they arrive with the models in M1). Ruff now treats the repo root as a source root so `tests` imports sort correctly.
