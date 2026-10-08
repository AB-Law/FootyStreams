---
id: 0182
date: 2026-10-08
type: test
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Stop the season tests timing out under coverage
---
The PR-tier run (coverage, parallel workers) pushed a two-season test over the 30 second
limit. The same-seed and different-seed season tests now allow 120 seconds and reuse the
cached four-club season instead of playing an extra one.
