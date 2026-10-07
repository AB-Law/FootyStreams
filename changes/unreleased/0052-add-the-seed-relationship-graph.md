---
id: 0052
date: 2026-10-07
type: added
scope: [seed]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the seed relationship graph
---
Squad friendship clusters, veteran-to-prospect mentors, rival pairs, manager trust in key players and the board, derby-pair manager rivalries, one kin pair that shares a surname, and the crew's scripted duos, feud, mentor, club affinities and favourite/disliked players. Symmetric kinds are canonicalised (a.id < b.id); no self links or duplicates. About 250 rows for 8 clubs rather than the ~600 the design estimated: the M1 relationship model is smaller than the design table.
