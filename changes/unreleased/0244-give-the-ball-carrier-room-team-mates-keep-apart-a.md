---
id: 0244
date: 2026-10-09
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: 'Give the ball carrier room: team-mates keep apart and nobody swarms a goalkeeper'
---
Team-mates aim away from each other (spacing_m) and from the man on the ball (carrier_space_m); only players within press_range_m press, one man shows a goalkeeper the way and stops at the edge of the box. Players within 6 m of the carrier in 4+ at once fell from 2% of frames to under 1%.
