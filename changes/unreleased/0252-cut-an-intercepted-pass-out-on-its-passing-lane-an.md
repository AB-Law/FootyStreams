---
id: 0252
date: 2026-10-09
type: fixed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: patch
sim_version_impact: patch
config_impact: false
migration: false
summary: Cut an intercepted pass out on its passing lane and keep the viewer ball on the frame's flight
---
An interceptor used to take the ball where he stood, so a pass looked like it was played to an opponent. He now meets it on the nearest point of the passing lane. The viewer follows the frame's ball when nobody is on it, so a pass no longer waits at the passer and then jumps.
