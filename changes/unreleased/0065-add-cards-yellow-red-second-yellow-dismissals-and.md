---
id: 0065
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add cards: yellow, red, second yellow, dismissals and the emergency keeper'
---
Yellow above a threshold that falls with the referee's card tendency and strictness; straight red above 0.90 severity or a denied chance (60%); second yellow is a red. Sent-off players leave team.players (men counts drop), a sent-off keeper is replaced by the best-handling outfielder, and no side is reduced below 7 (no further cards).
