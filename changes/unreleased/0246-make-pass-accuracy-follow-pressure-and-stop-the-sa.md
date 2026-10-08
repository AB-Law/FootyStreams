---
id: 0246
date: 2026-10-09
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: Make pass accuracy follow pressure and stop the same two players passing back and forth
---
A clear pass is near-certain: pressure on the passer and receiver closedness bite on curves (pressure_exponent, openness_exponent), scaled by pass length; short passes lose nothing to distance. A pass straight back to the man who gave the ball loses utility that grows with each return in a row (return_pass_penalty), a free runner ahead earns a bonus, gaining ground is rewarded, choices are less scattered (temperature_scale 1.4). Retuned shot quality, box fouling and shot appetite. Back-and-forth runs of 3+ passes between the same two fell from 80-98 a match to 0.
