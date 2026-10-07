---
id: 0070
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add club finance and the ledger
---
Finance produces postings for matchday gate, hospitality and merchandise, weekly wages, sponsor and broadcast instalments, facilities and academy costs, debt interest, and season-end prize money and broadcast merit. ledger.book writes the entries and moves each balance by exactly their sum. ticket_price_scale in league.yaml sizes gate income to about 30% of a club's income.
