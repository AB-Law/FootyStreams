---
id: 0048
date: 2026-10-07
type: added
scope: [sim, events]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the match clock helpers and the event emitter
---
events/clock.py converts playing seconds to the displayed MatchClock (and back) incl. stoppage; sim/emit.py numbers, stamps and validates every event through the discriminated union (no trusted shortcut). No schema change.
