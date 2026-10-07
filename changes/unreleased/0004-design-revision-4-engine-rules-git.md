---
id: 0004
date: 2026-10-07
type: changed
scope: [design, ci, tools]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Revise design for extensible tactics, attribute types, voice, runtime engine; add agent rules, end-of-turn gate and git workflow.
---
Review feedback applied:

- `01-entities`: replaced the shared `Rating` alias with semantic types (`Attribute`, `Competence`, `Reputation`,
  `Disposition`, `Level`, `AbilityScore`); added the derived `PlayerProfile` (role ratings, strengths, signature
  skills); `TeamTactics` is now a versioned module registry with per-phase shapes, player instructions, situational
  plans and extensions; `VoiceProfile` redesigned.
- New `12-voice-and-tts.md` (human-sounding commentary, provider landscape, bake-off plan; no provider chosen) and
  `13-runtime-engine.md` (the long-running engine replaces "run a CLI" as the primary executable; CLIs stay as thin
  dev/ops tools). Milestones now M0-M14 with a PR slice plan per milestone.
- Agent rules are authored once in `.claude/rules/` and generated into `.cursor/rules/` by
  `tools/rules_sync.py`; `AGENTS.md` is now a short index. `.claude/settings.json` and `.cursor/hooks.json` install an
  end-of-turn Stop hook (`tools/hooks/gate.py`) that runs `uv run check` and blocks until it passes (no-op until
  `pyproject.toml` exists; retry cap 8 with a loud give-up notice). Gate script tested against pass, fail, cap,
  unchanged-skip and missing-command scenarios for both agents.
- Git workflow (branches, atomic commits, small PRs, rebase-and-merge) added to `11-engineering-standards.md` and
  `.claude/rules/git-workflow.md`; `.github/pull_request_template.md` added; `.gitignore` added.
