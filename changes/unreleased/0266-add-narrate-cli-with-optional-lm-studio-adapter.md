---
id: 0266
date: 2026-10-09
type: added
scope: [cli]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add narrate CLI with optional LM Studio adapter
---
`uv run narrate --home A --away B` simulates the friendly, packs the brief, and writes
`commentary.json`. `--engine template` (default) is offline; `--engine lmstudio` calls a local
LM Studio OpenAI-compatible server (`http://127.0.0.1:1234/v1/chat/completions`) and falls back
to templates on any failure.
