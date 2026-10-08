---
id: 0183
date: 2026-10-08
type: test
scope: [seed]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Skip the world-gen wall-clock tripwire under coverage
---
Under the PR-tier coverage run, generate_world takes about 12-15 s against a 10 s slack
budget. Identical-content for the same seed is still asserted; the wall-clock tripwire is
skipped when a tracer is active, matching the sim budget tripwire.
