---
id: 0156
date: 2026-10-07
type: added
scope: [cli]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the league command
---
uv run league plays the current season of a seeded world (--seed/--clubs, --world DIR, or --db PATH to resume a SQLite database) and prints the table and each club's money; --matchday N stops after that matchday. Reports are pure functions in league/report.
