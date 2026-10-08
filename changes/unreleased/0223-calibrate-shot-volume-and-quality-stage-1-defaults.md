---
id: 0223
date: 2026-10-08
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: 'Calibrate shot volume and quality: stage 1 defaults'
---
Eight defaults move so a league plays about 2.7 goals, 13 shots a side and 10 corners a match (was 4.0 goals, 21 shots, 15 corners): shot.min_xg 0.02 to 0.06, dribble.base 0.55 to 0.3235, dribble.distance_m 8 to 8.54, decision.progress_scale 12 to 12.94, decision.shot_scale 14 to 10.68, decision.clear_pressure 0.45 to 0.61, passing.base_back 1.0 to 0.925, offside.mistime_base 0.7 to 0.5. Found by a damped Gauss-Newton fit from the sensitivity sweeps and checked on 1,200 fresh matches: 18 of 43 metrics pass (was 13), loss 12.3 (was 24.5).
