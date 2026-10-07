---
id: 0142
date: 2026-10-07
type: added
scope: [data]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add league config, calendar, double round-robin schedule and standings with tie-breaks
---
data/static/league.yaml and mood.yaml with typed config models; calendar dates (matchday every 21 days so 14 matchdays plus the off-season fill one in-world year - weekly matchdays would age players several times a season; flagged as a deviation); circle-method schedule with Berger orientation and a flip search that keeps venue streaks at two or fewer and derbies off matchday 1 (valid for 2-20 clubs, hypothesis over seeds); W12 check in verify; league table with points, goal difference, goals scored, head-to-head mini league, then club id.
