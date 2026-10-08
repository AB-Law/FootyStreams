---
id: 0129
date: 2026-10-07
type: added
scope: [data]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add the club generator: identity, stadium, finances, organisation, calibrated squads and default tactics'
---
Eight club archetypes (data/static/club_archetypes.yaml) drive each club's identity, ground, fanbase, finances (income, wage budget, sponsors, debt, opening ledger), board, facilities, academy and culture. The squad generator retries with a corrected quality until the best XI's team rating lands on the archetype target, rolling back names and ids of discarded attempts; wages are scaled so the bill hits the archetype's share of the wage budget (Boom & Bust overspends on purpose). Default tactics are the manager's preset in his preferred formation, pulled towards his philosophy.
