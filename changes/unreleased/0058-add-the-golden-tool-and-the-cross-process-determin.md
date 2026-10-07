---
id: 0058
date: 2026-10-07
type: added
scope: [cli, sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the golden tool and the cross-process determinism test
---
uv run golden check|update pins the log digest of three (pairing, seed) cases in tests/golden/digests.json; update refuses to rewrite changed digests unless SIM_VERSION was bumped. A subprocess test compares ndjson bytes under two PYTHONHASHSEED values.
