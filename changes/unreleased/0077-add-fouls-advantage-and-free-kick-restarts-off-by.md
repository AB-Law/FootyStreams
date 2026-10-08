---
id: 0077
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add fouls, advantage and free-kick restarts (off by default until M5 is enabled)
---
Challenges (press tackles and tackled dribbles) roll for foul-worthy contact, severity and the referee's call from the discipline stream. A called foul emits tackle(outcome foul) then foul, then advantage (no restart) or a free kick for the fouled side. DisciplineConfig.contact_base is 0 for now so M4 output and goldens are unchanged; the commit that enables M5 raises it and bumps SIM_VERSION.
