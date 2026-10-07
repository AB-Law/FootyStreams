---
id: 0044
date: 2026-10-07
type: added
scope: [domain]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add ability_from_attributes and best-lineup squad strength helpers
---
ability_from_attributes lets generators and development evaluate hypothetical attribute sets without building a Player (compute_current_ability now delegates to it; behaviour unchanged). squad_strength picks the best XI for a set of tactical slots and rates it; the seed generator, the world checks and the lineup AI share it.
