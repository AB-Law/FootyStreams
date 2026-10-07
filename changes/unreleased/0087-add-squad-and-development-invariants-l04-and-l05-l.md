---
id: 0087
date: 2026-10-07
type: added
scope: [verify]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add squad and development invariants L04 and L05; league --seasons
---
L04 every club keeps a legal senior squad with enough keepers; L05 ability never exceeds potential, the development journal stays bounded and retirees have no contract. uv run league --seasons N plays N seasons with the off-season rollover between them.
