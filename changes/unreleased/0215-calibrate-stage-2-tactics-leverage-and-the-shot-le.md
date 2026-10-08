---
id: 0215
date: 2026-10-08
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: 'Calibrate stage 2: tactics leverage and the shot level'
---
With the seeded tactics a high-press, high-line, attacking side beat better teams (GAT, rating -9, took 1.95 points a match against 1.27 for a +3 side) and a patient side took 3 shots a match: style choices had benefits and no costs, so tactics outweighed quality. Mentality, directness, defensive line and press leverage (decision.mentality_swing, decision.directness_bias, positioning.line_range, pressure.radius_range_m) drop to a tenth of their stage 1 values, which makes club rating predict points (Spearman 0.21 to 0.9). The volume knobs were refitted with the leverage fixed. On 1,200 fresh matches 28 of 43 metrics pass (was 18), loss 4.2 (was 12.3); medium and large gap favourites win 61% and 72% (targets 60.5 and 73).
