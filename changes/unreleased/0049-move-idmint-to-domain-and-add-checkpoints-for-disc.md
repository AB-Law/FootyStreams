---
id: 0049
date: 2026-10-07
type: refactor
scope: [seed]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Move IdMint to domain and add checkpoints for discarded generation attempts
---
Both seed and league mint ids and neither may import the other, so IdMint (with extra prefixes for ledger entries, world events, modifiers, windows and transfers) lives in domain/ids.py. IdMint and NameBook can snapshot and restore their state so a calibration attempt that is thrown away leaves no trace.
