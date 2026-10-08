---
id: 0240
date: 2026-10-09
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: Make players press, mark and keep moving; keep everyone off the touchline
---
Positions refresh every 2 s (was 4 s). The nearest defenders close the ball down, the rest pick up a man goal-side, and every outfield player loops slowly round his slot (movement.py; no sin/cos, no random draws). Targets stay off the touchlines by edge_margin. Retuned the knobs the new pressure moved: challenge attempt rate and radius, foul contact and booking thresholds, mistimed-offside share, restart shares, cross bias and shot scale. Measured on 112 matches against the realistic profile (see docs/milestones/M8.md). SIM_VERSION 0.6.0.
