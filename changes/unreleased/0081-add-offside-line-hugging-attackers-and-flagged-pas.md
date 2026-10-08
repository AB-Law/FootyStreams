---
id: 0081
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add offside: line-hugging attackers and flagged passes with an indirect free kick'
---
OffsideConfig.enabled (off until M5 is enabled). The line is the second-last defender in the attackers' frame; attackers stand just short of it (sharper off-ball movers closer); a completed pass to a receiver beyond line and ball is flagged with probability 0.88 + 0.10 x referee consistency (discipline stream), emitting pass(complete), offside, then an indirect free kick for the defenders.
