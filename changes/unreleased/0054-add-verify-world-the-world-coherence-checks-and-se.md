---
id: 0054
date: 2026-10-07
type: added
scope: [seed]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add verify_world, the world coherence checks, and senior-squad nationality quotas
---
verify/world*.py implements W01 (foreign keys), W02 (squads, bench, formation coverage), W03 (ledger and wage bills), W07/W08 (registration, contracts, shirts), W09/W10 (ability) and seed coherence checks C01-C08 (names, nationality mix, referees, crew, managers, prospects, league shape). Every check has a canary test that mutates a valid world to prove it can fail; coverage of verify/ is 100%. The generator now plans each senior squad's nationalities up front (10-13 Valmerians, the rest from 3-5 foreign nations, none above 55%), which the coherence check demands. The schedule check (05 section 5 item 9) moves to M9 where the schedule lives. WorldRng-based tests share cached worlds.
