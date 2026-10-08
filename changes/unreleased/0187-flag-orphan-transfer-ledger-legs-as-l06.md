---
id: 0187
date: 2026-10-08
type: fixed
scope: [verify]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Flag orphan transfer ledger legs as L06
---
L06 only walked Transfer rows, so ledger legs with a transfer_id and no matching transfer were invisible.
