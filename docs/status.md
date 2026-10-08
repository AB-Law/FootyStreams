# Project status

Updated at the end of milestone M1 (local, awaiting review — 2026-10-08). Read this first; then the design section for your task.

## Where we are
- Design is complete (`docs/design/`, index in `docs/design/README.md`; decisions in `09-schema-decisions.md`).
- **M0 is merged** to `main` (scaffold, quality gate, changelog, CI, ADRs).
- **M1 (domain models and schema export) is implemented** on local branch `feat/m1-domain-models`
  awaiting the owner's review before push / one PR. See `docs/milestones/M1.md`.
- **Next after M1 merges: M2 ∥ M4** (seed/world generators and sim kernel) as parallel tracks —
  one branch and one PR per milestone, not stacked slice PRs.

## How to work here
```bash
uv sync
git config core.hooksPath .githooks   # once per clone
uv run check                           # fast gate (about 10 s); --tier pr adds coverage
uv run changelog new "Imperative summary" --type added --scope sim --milestone M2
uv run changelog build                 # regenerate CHANGELOG.md after adding/changing fragments
uv run export-schemas                  # regenerate schemas/ after model changes
uv run pr-size --base origin/main      # informational for milestone PRs
```
- Workflow: branch from `main`, atomic Conventional Commits, gate green, **stop for the owner's review**, only
  then push and open a PR (`.claude/rules/git-workflow.md`). Never push or open a PR without that approval.
- A Stop hook runs `uv run check` after every agent turn and blocks until it passes.

## What exists (src/footystreams)
| Package | State |
|---------|-------|
| `domain` | Full M1 models: types, person/player, ratings/valuation, tactics, club, competition, match, world/transfer/dev, media; `SCHEMA_VERSION` / `SIM_VERSION`; usage registry |
| `events` | MatchEvent discriminated union, summary, MatchResult |
| `cli` | `export-schemas` (argparse) |
| `sim`, `league`, `persistence`, `extensions`, `analytics`, `runtime`, `seed` | Empty skeletons; layering rules enforced |
| `verify` | `Violation` type only |
| `tools` | `check`, `architecture`, `changelog` (incl. SCHEMA_VERSION bump policy), `commitmsg`, `prsize` |

Also: committed `schemas/` (drift-tested), factories/strategies under `tests/`, `tools/hooks/gate.py`,
`.githooks/`, `.github/workflows/ci.yml`, ADRs, glossary.

## Known issues and caveats
- CI / branch protection checklist from M0 still applies where not yet configured on GitHub.
- The architecture checker matches imports by name (aliases like `import math as m` are not tracked).
- Claude and Cursor rule files are maintained by hand in pairs (`.claude/rules` and `.cursor/rules`).
- Mood caps are named defaults only until `mood.yaml` (M2/M9).

## Track A: match engine (updated at the end of M4, overnight run)
- **Branch chain (draft PRs, each based on the previous):** `feat/m4-sim-kernel` (base `main`) -> `feat/m5-dead-balls-discipline` -> `feat/m6-fatigue-injuries-weather-ai` -> `feat/m7-summary-ratings-frames`.
- **M4 done locally:** `simulate_match` / `run_match` over factory teams (`SimRng`, `SimConfig`, positioning, pressure, decision model, pass/dribble/tackle/interception/clearance/shot/save/goal, kickoff/halftime/fulltime, event-derived summary). `uv run sim --demo --seed 7`, `uv run golden check|update`, `verify.verify_match` (M01-M05, M10, M17). `SIM_VERSION` 0.1.1, `SCHEMA_VERSION` 0.1.4. Report: `docs/milestones/M4.md`; implementation notes: `docs/design/02-simulation.md` section 16.
- **Known gaps:** no dead balls/fouls/cards (M5), fatigue/injuries/subs/weather (M6), ratings/frames/tags (M7). ~0.4 s CPU per match (budget 0.15 s, M8 optimises). Calibration is rough (M8).
- **Merge notes:** fragment ids 0042+ may collide with Track B; `verify/__init__.py` and `pyproject.toml` scripts (`sim`, `golden`) and `domain/versions.py` are shared files to merge by hand.

### Track A update at the end of M5
- **M5 done locally** on `feat/m5-dead-balls-discipline` (based on the M4 branch): referee model, fouls, advantage, cards and dismissals, throw-ins, goal kicks, corners with an aerial duel, penalties, free-kick shots and crosses, offside, announced added time; `verify_match` gains M07 (in part), M11, M12. `SIM_VERSION` 0.2.0, `SCHEMA_VERSION` 0.1.5. Report: `docs/milestones/M5.md`.
- Known gaps: red cards in band for even teams, about 2x the band in the varied sweep; second-half added time short (substitutions and injuries arrive in M6); 0.37 s CPU a match.

### Track A update at the end of M6
- **M6 done locally** on `feat/m6-fatigue-injuries-weather-ai` (based on the M5 branch): fatigue, weather and pitch, home advantage (crowd), injuries with forced changes, substitution mechanics, the AI manager (checkpoints, triggers, mentality changes, changes at stoppages and half-time); `verify_match` gains M06, M08 (M07 and M11 extended; M09 is an engine-level test). `SIM_VERSION` 0.3.0, `SCHEMA_VERSION` 0.1.6. Report: `docs/milestones/M6.md`.
- Fixed on the way: an away-side positioning edge from sequential team updates.
- Known gaps: no formation changes or half-time talk in the manager; the factory bench (two outfielders and a goalkeeper) caps changes at about 3.5 a match; draw rate and red cards still high; 0.4 s CPU a match.

### Track A update at the end of M7
- **M7 done locally** on `feat/m7-summary-ratings-frames` (based on the M6 branch): the causal context (momentum, intensity, significance, tags), enriched pass/dribble/shot events, the full summary (stats, ratings 3-10, player of the match, hooks, pass matrix, zone flow, shot map, xG/xA/xT, timelines, key moments, injuries), opt-in tracking frames, a read-only `analytics/` module (maps, totals, heatmaps, `annotate`), and `verify` M13-M16 and M18. `SIM_VERSION` 0.4.0, `SCHEMA_VERSION` 0.2.0 (additive, defaults only; flagged in the PR). Report: `docs/milestones/M7.md`.
- Track A is complete (M4-M7). Next on this track: M8 (balance harness, calibration, performance), then M9 needs the league layer (`build_match_setup`, lineup AI).
- Known gaps: about 0.5 s CPU a match (budget 0.15 s), draw rate and red cards high, manager has no formation changes or half-time talk, hooks that need league context.
