---
id: 0011
date: 2026-10-07
type: added
scope: [tools, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add documented package skeletons per layer and an architecture checker with canary tests.
---
Creates the layer packages from `docs/design/04-architecture.md` (`domain`, `events`, `sim`, `league`,
`persistence`, `extensions`, `verify`, `analytics`, `runtime`, `cli`, `seed`) with docstrings stating their
responsibility and allowed imports. `footystreams.tools.architecture` checks the source tree: layering (data in
`rules.py`), purity of the pure layers (no I/O, wall clock, randomness, numpy), libm-backed maths and
`hash()`/`id()` in `sim`, unknown packages and the 400-line module limit. The rules are tested on the real tree and
by canary tests that feed deliberately bad modules, so the gate cannot silently become a no-op. Relative imports are
now banned by ruff. Known limit: aliased imports (`import math as m`) are not tracked.
