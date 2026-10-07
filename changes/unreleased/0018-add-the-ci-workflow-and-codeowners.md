---
id: 0018
date: 2026-10-07
type: build
scope: [ci]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the CI workflow and CODEOWNERS
---
GitHub Actions runs 'uv run check --tier pr' on Ubuntu and Windows with Python 3.12 and 3.13 for every pull request and push to main (full git history so the change-log check can compare with origin/main), plus a pull request size job (target 400, hard cap 800; the 'large-approved' label allows more). Default token permissions are read-only. Guard tests parse the workflow so it cannot silently drift from the local gate. NOTE: the workflow can only be proven by its first real run on GitHub; action versions (checkout v4, setup-uv v5) were chosen from memory.
