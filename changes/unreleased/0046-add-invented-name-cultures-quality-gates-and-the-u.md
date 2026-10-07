---
id: 0046
date: 2026-10-07
type: added
scope: [data]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add invented name cultures, quality gates and the unique name book
---
14 invented cultures (6 regions of Valmere, 8 foreign nations) as syllable grammars, pronunciation hints, culture trigram distinctness test, a ~680-entry real-world denylist (design asked for ~1,000; it is a safety net, the grammars are synthetic) and a profanity blocklist. known_as is unique world-wide; a surname repeats at most twice unless kin.
