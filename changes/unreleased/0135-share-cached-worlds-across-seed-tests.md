---
id: 0135
date: 2026-10-07
type: test
scope: [cli]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Share cached worlds across seed tests
---
World generation takes about 2.3 s, so tests share one world per seed (tests/factories/world.make_world) and the CLI tests reuse it; the subprocess test still runs the real generator end to end. Keeps the fast tier near 40 s.
