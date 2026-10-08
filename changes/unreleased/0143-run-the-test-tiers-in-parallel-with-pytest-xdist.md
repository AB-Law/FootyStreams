---
id: 0143
date: 2026-10-07
type: build
scope: [tools]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Run the test tiers in parallel with pytest-xdist
---
The fast tier had grown to about 50 s (budget 60 s) with the seed and persistence suites; -n auto brings it to about 20 s on 4 cores. Test order stays random (pytest-randomly); module-level caches are per worker. No test or threshold changed.
