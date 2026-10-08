---
id: 0241
date: 2026-10-09
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: Stop attackers in the final third passing the ball sideways and straight back
---
A pass in the final third that gains no threat loses box_recycle_penalty, and one that hands the ball straight back to the man who gave it loses ping_pong_penalty on top, so a forward pass, a dribble or a shot wins.
