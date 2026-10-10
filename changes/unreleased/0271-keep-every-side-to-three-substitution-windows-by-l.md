---
id: 0271
date: 2026-10-09
type: fixed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: patch
sim_version_impact: patch
config_impact: true
migration: false
summary: Keep every side to three substitution windows by letting a manager make several changes at one stoppage
---
The M8 calibration raised `manager.max_windows` to 5 because the AI made one change per stoppage. The rule is five changes in three windows, and invariant M08 enforces it: 173 of 200 default-world matches broke it, so the runtime's pre-air gate quarantined nearly every match and `uv run engine` put no match on air (`tests/unit/cli/test_engine_cli.py`, slow tier, failed with `[M08] away used 4 windows`).

After a change of players a manager now looks again at the same stoppage and may make another, so a batch shares one window, and `max_windows` is 3 again. In 200 matches no side uses more than three windows; a side makes 4.60 changes (band 3.5 to 4.9, target 4.2; 4.04 before). A 1,200-match balance run passes 32 of 43 metrics against 31 before.

`config_impact`: the `manager.max_windows` default changes from 5 to 3. `SIM_VERSION` 0.7.7, `SCHEMA_VERSION` 0.8.1 (the exported schemas carry the version defaults); goldens re-pinned. Regression: `tests/regressions/test_0271_*` pins the sim's limits to `MatchRules` and plays three league matches that used four or five windows. Design 02 sections 7 and 11 and the M8 report deviation 2 are updated.
