---
id: 0016
date: 2026-10-07
type: test
scope: [tools, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add unit tests for the end-of-turn quality gate hook
---
The Stop hook (tools/hooks/gate.py) is tested against: project not set up yet, failing checks for Claude (exit 2) and Cursor (followup message), aborted Cursor turns, pass and green-state caching, skip when nothing changed, re-run after a change, missing command, timeout, the retry cap with its loud give-up notice, unlimited retries, counter reset on a pass, fingerprint behaviour and tolerant payload parsing. tools/ and tools/hooks/ became packages so tests can import the script; it remains standard-library only.
