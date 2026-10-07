---
id: 0176
date: 2026-10-07
type: added
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the transfer market
---
TransferStage runs on every day a window is open: clubs rank their needs, shortlist players from other clubs, free agents and the outside world by what they perceive of them, negotiate a fee over up to three rounds and wage terms with the player, pass the medical and sign. Clubs list surplus, unhappy and (in financial trouble) valuable players; outside clubs bid for the league's best. A reserved outside-world club makes every fee a two-sided ledger leg. The day's changes are one delta, so a transfer is atomic; on the last day squads are brought to a legal size.
