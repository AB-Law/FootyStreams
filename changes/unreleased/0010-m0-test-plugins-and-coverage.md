---
id: 0010
date: 2026-10-07
type: build
scope: [tools, ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add test plugins, Hypothesis profiles, a coverage floor and the 'pr' tier of 'uv run check'.
---
Dev dependencies: pytest-randomly (random order), pytest-timeout (30 s per test), pytest-socket (no network except
loopback), pytest-cov, pytest-xdist, hypothesis. Hypothesis profiles `dev`/`ci`/`nightly` are selected with
`HYPOTHESIS_PROFILE` and have no deadlines (timing must never make a test flaky). Pytest runs in importlib mode so
test modules may share base names. Coverage is branch coverage with a 90% floor; `uv run check --tier pr` runs the
suite under coverage. Per-module 100% floors for critical modules arrive with those modules.
