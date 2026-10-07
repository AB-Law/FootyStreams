---
id: 0042
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add SimRng (xoshiro256**) and exact-arithmetic mathx helpers
---
Self-contained integer PRNG because `random` is banned in sim (ADR 0005); known-answer, fork-isolation and draw-counter tests. mathx: clamp, squash, lerp, distance, rational_weight.
