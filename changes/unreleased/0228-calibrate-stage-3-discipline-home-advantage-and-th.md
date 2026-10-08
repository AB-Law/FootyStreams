---
id: 0228
date: 2026-10-08
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: 'Calibrate stage 3: discipline, home advantage and the on-target share'
---
yellow_base 0.70 to 0.665 (yellows 2.2 to 3.4 a match; the response is steep, 0.5 gives 10), second_booking_margin 0.04 to 0.10 (second yellows: reds 0.2 to 0.15), box_caution 0.35 to 0.5 and contact_base 0.9 to 1.0 (fouls and penalties), shot.off_target_base 0.43 to 0.48 (on target 0.45 to 0.40) and home_advantage.crowd_lift 0.12 to 0.25 (home goals 1.33 to 1.46, home wins 38 to 42%). Found by direct scans of the levers the Gauss-Newton fit could not move. On 1,200 fresh matches 33 of 43 metrics pass (was 28), loss 1.2 (was 4.2).
