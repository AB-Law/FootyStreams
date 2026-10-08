---
id: 0086
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Bound the M5 SimConfig knobs like the M4 ones
---
The referee, discipline, restarts, offside and stoppage groups used plain floats, so `merge_config` (the balance harness) could build a config that divides by zero (`call_scale` 0) or yields a negative restart delay. They now use the shared `Share` / `Positive` / `NonNegative` types (moved to `sim/config_types.py`), and validators keep each min/max pair ordered. No default changed: output and `config_hash` are untouched.
