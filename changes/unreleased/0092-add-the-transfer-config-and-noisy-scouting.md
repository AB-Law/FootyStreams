---
id: 0092
date: 2026-10-07
type: added
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the transfer config and noisy scouting
---
transfer.yaml holds scouting, valuation, needs, terms, medical, window, sales and outside-world parameters. perceive() gives a club's estimate of a player's ability and potential with an error that shrinks linearly with its judging ability and is larger for potential.
