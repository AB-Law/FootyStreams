---
id: 0255
date: 2026-10-09
type: added
scope: [events, sim]
milestone: M8
breaking: false
schema_version_impact: minor
sim_version_impact: patch
config_impact: false
migration: false
summary: Give tracking frames player velocity and the ball's height
---
Each frame player now carries vx and vy (metres per second over the last interval) and each frame the ball's height above the grass, so a renderer can curve runs, face players the way they go and lift a long pass. Frames are off by default; the only change to a default match is the schema version in its kickoff event.
