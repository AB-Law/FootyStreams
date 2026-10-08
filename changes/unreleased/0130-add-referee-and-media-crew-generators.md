---
id: 0130
date: 2026-10-07
type: added
scope: [data]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add referee and media crew generators
---
Ten match officials (a card-happy one, a lenient old hand, a home-bias outlier and one who leans away; home bias averages about +0.1) and an eleven-person broadcast crew instantiated from authored personas (data/static/media_archetypes.yaml) with distinct personalities, casting sheets, placeholder voice bindings with unique ids and pronunciation lexicon entries. Catchphrases are plain text: the M1 media model has no trigger tags to validate.
