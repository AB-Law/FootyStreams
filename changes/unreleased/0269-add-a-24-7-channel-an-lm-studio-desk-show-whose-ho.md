---
id: 0269
date: 2026-10-10
type: added
scope: [cli, extensions, docs]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: 'Add a 24/7 channel: an LM Studio desk show whose hosts remember'
---
Adds the 24/7 channel prototype: uv run channel keeps a feed of desk segments written by LM Studio only (match previews and recaps from fixtures it simulates, club histories, manager and player files, the table, banter) on a wall-clock schedule, and the Channel page (viewer/channel.html) plays what is on air. The hosts remember through a JSON show bible in the MemoryRecord shape (results, settled predictions, running jokes, opinions); the model may phrase facts but replies are rejected for numbers not in the facts, world names the segment does not involve, repeated lines and missing picks. The feed carries the ticker and memories as of each segment and teaser titles, so a viewer never sees ahead of the broadcast. Shared LM Studio client in cli/lm_client.py (the narrator uses it too, and reasoning_effort none is sent so reasoning models answer); extensions/pack.py exposes manager_career_line and player_career_line. Design in docs/design/15-the-channel.md. No engine, schema or sim change. Verified by unit tests (rundown, memory, replies, feed, producer with a scripted model, the loop with a fake clock, the client) and a live run against qwen3.5-9b.
