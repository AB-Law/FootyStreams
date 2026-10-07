# Changelog

> Generated from `changes/` fragments by `uv run changelog build` (tool arrives in M0). **Do not edit by hand once the generator exists** — add a fragment instead (see `changes/README.md`). Until then this file is compiled manually from the fragments.

Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: SemVer for the project; `SIM_VERSION` and `SCHEMA_VERSION` are tracked separately and recorded on every match.

## [Unreleased]

### Build / Tooling
- **0009** Replace .gitignore with a complete Python, tooling and project ruleset. *(M0; scope: tools)*
- **0007** Add the uv project, strict lint/type/test configuration and the 'uv run check' quality gate. *(M0; scope: tools, ci)*

### Docs / Design
- **0006** Make .claude/rules the source of agent rules and generate .cursor/rules from it; remove docs/rules. *(design; scope: design, tools)*
- **0005** Require a human review checkpoint before any push or pull request; record the GitHub remote. *(design; scope: design, ci)*
- **0004** Revise design for extensible tactics, attribute types, voice, runtime engine; add agent rules, end-of-turn gate and git workflow. *(design; scope: design, ci, tools)*
- **0003** Add testing strategy, live-channel operational safety, engineering standards and the change-fragment log system. *(design; scope: design, ci)*
- **0002** Revise design after review - mood system, transfers and development, tunable balance targets, roadmap, decision log. *(design; scope: design)*
- **0001** Add the Phase 1 design document set (entities, simulation, events, architecture, seeding, milestones). *(design; scope: design)*

Versions at this point: package 0.0.1 (tooling only) · `SIM_VERSION` n/a · `SCHEMA_VERSION` n/a.
