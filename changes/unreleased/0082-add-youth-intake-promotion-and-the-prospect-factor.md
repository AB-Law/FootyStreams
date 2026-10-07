---
id: 0082
date: 2026-10-07
type: added
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add youth intake, promotion and the prospect factory
---
The league asks for new players through a ProspectRequest/ProspectFactory contract in domain; seed.prospects builds them with the seed generators (names unique against the world, ids derived from the request key). youth.py plans each academy's intake from its quality and the league level, signs prospects on youth deals and promotes them as validated seniors.
