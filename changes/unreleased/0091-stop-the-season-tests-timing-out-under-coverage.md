---
id: 0091
date: 2026-10-07
type: test
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Stop the season tests timing out under coverage
---
The PR-tier run (coverage, parallel workers) pushed a two-season test over the 30 second limit. Season-building test modules now allow 120 seconds, and two tests reuse the cached season instead of playing a third.
