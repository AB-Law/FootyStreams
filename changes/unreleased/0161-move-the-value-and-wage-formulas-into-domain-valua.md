---
id: 0161
date: 2026-10-07
type: refactor
scope: [domain]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Move the value and wage formulas into domain.valuation
---
market_value_of and wage_from_value lived in seed but league needs them too (youth contracts, free-agent signings, progression); they move to domain.valuation unchanged, so seeded worlds are byte-identical.
