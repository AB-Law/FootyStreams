---
id: 0120
date: 2026-10-08
type: fixed
scope: [events, sim]
milestone: M7
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Fix own-goal tags and bound the M7 context knobs
---
An own goal no longer counts toward its scorer's brace or hat-trick tag (the tally and the hooks already excluded it), the context knobs progressive_frame_x and big_chance_xg are bounded to (0, 1] like every other SimConfig knob, and the tally shares the context tracker's big-chance threshold instead of repeating the literal. Defaults and golden digests are unchanged.
