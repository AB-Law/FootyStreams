---
id: 0002
date: 2026-10-07
type: changed
scope: [design]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Revise design after review - mood system, transfers and development, tunable balance targets, roadmap, decision log.
---
Decisions from review: pass-level events; byte-identical determinism across Windows and Linux; SQL with real
columns plus validated JSON documents (clarified: not NoSQL); full schema up front.

Added `07-world-systems.md` (daily tick, StateModifier mood system with hard caps, player development,
contracts, transfers with a synthetic outside-world market, season rollover), `08-roadmap.md` (gegenpressing,
triangles, pass maps, frame data, learning AI managers, cup play, youth teams), and `09-schema-decisions.md`
(18 locked decisions; manager sack/hire is schema-only; frame events default to 1 s).

Balance targets became profile-based and tunable (`balance_targets.yaml`, sensitivity and fit tooling). Milestones
extended to M0–M12. Events gained the opt-in `frame` type and analytics-ready summary stats.
