---
id: 0177
date: 2026-10-07
type: added
scope: [verify]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the transfer-leg invariant L06 and the transfers report
---
L06 checks every paid transfer has an equal and opposite buyer and seller leg and a free one has none. uv run league --transfers lists the completed transfers.
