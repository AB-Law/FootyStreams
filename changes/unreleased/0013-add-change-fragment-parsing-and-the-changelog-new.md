---
id: 0013
date: 2026-10-07
type: added
scope: [tools]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add change fragment parsing and the 'changelog new' command
---
Fragments are validated on read (types, scopes, milestones, impact flags, one-line summary). 'uv run changelog new' creates the next numbered fragment; ids are literal strings so 0010 is not read as octal. A test parses every fragment in the repository. Check, build and release commands follow in the next slice.
