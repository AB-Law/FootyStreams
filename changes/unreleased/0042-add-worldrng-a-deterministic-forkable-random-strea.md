---
id: 0042
date: 2026-10-07
type: added
scope: [domain]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add WorldRng, a deterministic forkable random stream for seed and league code
---
SimRng lives in sim/ (parallel track A) and seed/league may not import sim, so a small SplitMix64 stream with the same interface (u, u_int, gauss, choice_weighted, fork) lives in domain/rng.py. Integer arithmetic and blake2b only: identical on every platform.
