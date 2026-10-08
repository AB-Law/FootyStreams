---
id: 0221
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: patch
config_impact: false
migration: false
summary: Hold attackers on the offside line and mistime runs only on balls in behind
---
Offsides ran at 14.7 a match against about 3.8 in a real league. Half came from attackers left beyond a line that had dropped (the ceiling limited only where they were heading); they are now pulled back each step. The other half came from the mistimed-run rule applying to every pass to a receiver on the line; it now applies to through balls, long balls and crosses. Measured over 112 matches: 14.7 to 5.1 a match; mistime_base is left for the fit.
