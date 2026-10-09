---
id: 0251
date: 2026-10-09
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: patch
sim_version_impact: minor
config_impact: true
migration: false
summary: Give every defender a job off the ball and have team-mates make angles for the carrier
---
Defenders who are not pressing now cut the passing lane to the most dangerous receiver, cover behind the presser, pick up a man or shift across to the ball side (sim/defending.py). Team-mates near the carrier take the most open of seven angles round him, so triangles form and break as defenders cut them off (sim/support.py). New PositionConfig knobs (lane_cut_*, cover_weight, free_mark*, balance_pull, support_*). Shot appetite is retuned (decision.shot_scale 8.6 to 15, shot.min_xg 0.06 to 0.055) so volume stays on target: over 300 matches shots per team 12.5, goals 2.55, pass completion 83%.
