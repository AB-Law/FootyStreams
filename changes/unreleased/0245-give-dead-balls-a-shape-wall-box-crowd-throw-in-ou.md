---
id: 0245
date: 2026-10-09
type: added
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: 'Give dead balls a shape: wall, box crowd, throw-in outlets, goal-kick spread'
---
setpiece_shape.py places the men involved in a throw-in, goal kick, corner, free kick or penalty and walks them there for the length of the stoppage; frames record a mid-moment keyframe so the build-up and the kick are shown separately, and the passer jogs on with the ball before he plays it. No random draw.
