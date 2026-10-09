---
id: 0260
date: 2026-10-09
type: added
scope: [events, sim]
milestone: M8
breaking: false
schema_version_impact: minor
sim_version_impact: patch
config_impact: false
migration: false
summary: Mark a shot taken with the head so a renderer can show a header
---
Shot events carry body_part, head for a corner met in the air and foot otherwise (only with the context on). It changes no outcome. record_match.py now also writes each player's preferred and weak foot into the replay meta file.
