---
id: 0132
date: 2026-10-07
type: added
scope: [seed]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: 'Add generate_world: the pure seed-to-World function'
---
generate_world(seed, GeneratorConfig) -> World ties the generators together: geography, a spaced-out league plan (archetypes shuffled by seed, target strengths at least 1.5 apart), eight calibrated clubs, 30 free agents, 4 unemployed managers, 10 referees, the broadcast crew, the relationship graph, rivalries, the competition and first season. About 2.3 s for the default eight-club world (budget 5 s).
