# Project status

Updated on the Join integration branch (2026-10-08). Read this first; then the design section for your task.

## Where we are
- Design is complete (`docs/design/`, index in `docs/design/README.md`; decisions in `09-schema-decisions.md`).
- **M0 is merged** to `main` (scaffold, quality gate, changelog, CI, ADRs).
- **Track A (M1, M4–M7)** and **Track B (M2, M3, M9–M11)** are both merged to `main`.
- **Join track:** the integration (PR 28), M8 part 1 (PR 29, the balance harness) and M12 (PR 30, the runtime engine, `uv run engine`) are merged. **M8 part 2** (`feat/m8-calibration`) is the calibration: 33 of 43 balance metrics pass (was 13), `SIM_VERSION` 0.5.0 and `SCHEMA_VERSION` 0.3.2, with the known gaps (goal timing, possession spread, corners) recorded in `docs/milestones/M8.md` and `tests/statistical`. Then M13 -> M14.
- **Living movement** (`feat/sim-realistic-play`, `SIM_VERSION` 0.6.0, `SCHEMA_VERSION` 0.4.0): pressing, marking, wander, box play and shot flights; see the follow-up in `docs/milestones/M8.md`. The 1,200-match statistical tier was not rerun.
- **Prototype (not a milestone):** `viewer/` is a silent pixel-art replay of a recorded match (TypeScript, outside the Python gate); see `viewer/README.md`.
- **Realistic look** (`feat/pixel-realism`, `SIM_VERSION` 0.7.4, `SCHEMA_VERSION` 0.6.0): frames run players at a sprint's pace and carry velocity and ball height; defenders have jobs off the ball (lane cuts, cover, balance) and attackers take and keep support angles; an intercepted pass is met on its lane; dribbles carry a `skill_move`. The viewer gained a broadcast side view, profile players, skill-move animations, live stats, lineups and tactical maps (see `viewer/README.md`). Not done: pass flight time and receivers running onto the ball in the sim, a frame rate above 1 Hz, defenders reacting to a skill move, and contact between players.
- Integration done: the sim plays the world's own formations (`sim.tables.tables_from_catalog`), `league --simulator event` plays a season on the real engine (deterministic; about 14 s for 4 clubs), and `sim --home A --away B --world DIR|--db FILE` plays a friendly (`league/friendly.py`).
- After M8 part 2: the real engine scores about 2.7 goals a match in the default world (target 2.7); the league's `EventSimulator` does not yet pass the match referee to `run_match` (a neutral one officiates; `sim --world` does pass it). Style choices have almost no effect on results until they have costs (a follow-up in the M8 report).

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
| `cli` | `export-schemas`, `seed`, `sim`, `league`, `golden` (argparse) |
| `sim`, `league`, `persistence`, `seed`, `verify` | Built by tracks A and B (see the sections below) |
| `extensions`, `analytics`, `runtime` | Empty skeletons; layering rules enforced |
| `tools` | `check`, `architecture`, `changelog` (incl. SCHEMA_VERSION bump policy), `commitmsg`, `prsize` |

Also: committed `schemas/` (drift-tested), factories/strategies under `tests/`, `tools/hooks/gate.py`,
`.githooks/`, `.github/workflows/ci.yml`, ADRs, glossary.

## Known issues and caveats
- CI / branch protection checklist from M0 still applies where not yet configured on GitHub.
- The architecture checker matches imports by name (aliases like `import math as m` are not tracked).
- Claude and Cursor rule files are maintained by hand in pairs (`.claude/rules` and `.cursor/rules`).
- Mood caps are named defaults only until `mood.yaml` (M2/M9).

---

## Track B (world) — overnight run, 2026-10-07
Track A (match engine) is built separately; the sections above predate both tracks. Track B builds M2, M3, M9, M10, M11 as **stacked draft PRs** (each branch is cut from the previous one).

| Milestone | Branch | State |
|-----------|--------|-------|
| M2 seed and static data | `feat/m2-seed-world` | done (draft PR); see `docs/milestones/M2.md` |
| M3 persistence | `feat/m3-persistence` | done; see `docs/milestones/M3.md` |
| M9 league layer | `feat/m9-league-layer` | done; see `docs/milestones/M9.md` |
| M10 development and rollover | `feat/m10-development-rollover` | done; see `docs/milestones/M10.md` |
| M11 contracts and transfers | `feat/m11-contracts-transfers` | done; see `docs/milestones/M11.md` |

### What M2 added
- `uv run seed --seed N [--out DIR] [--name NAME] [--clubs K] [--validate] [--world DIR]`; the committed `data/worlds/default` is seed 1 (`content_sha256` in its manifest).
- `seed/` (static loaders, names, players, managers, clubs, referees, media, relationships, `generate_world`, `world_io`), `verify/world*.py` (W01-W03, W07-W10, C01-C08), and in `domain/`: `WorldRng`, `IdMint`, `squad_strength`, world records and static-table models (**SCHEMA_VERSION 0.2.0**).
- Static tables in `data/static/`: formations, roles, traits, injuries, climate, name cultures, denylist/blocklist, player/club/media archetypes, manager styles, tactic presets.
- Tests share one world per seed through `tests/factories/world.make_world`; generation takes about 2.3 s.

### What M3 added
- `persistence/`: ports, table specs, codec, in-memory and SQLite backends, `UnitOfWork`, `WorldReader`, Alembic `0001_initial`; `uv run seed --db league.sqlite`. Contract tests in `tests/contract` run every behaviour on both backends.

### What M9 added
- `uv run league [--seed N] [--clubs K] [--world DIR] [--db PATH] [--matchday N]`: plays the current season (result-only simulator) and prints table and money; a SQLite `--db` is resumable.
- `league/`: schedule, standings, simulator seam, mood resolver, rule-based modifiers, life events, weather, attendance, lineup AI and `build_match_setup`, finance and `ledger.book`, `derive_world_delta`, `WorldDelta`, `WorldClock`, recovery, `DailyTick` (stage log, one transaction per stage and per match), `SeasonRunner`; `verify/league.py` (L01-L03), W12.
- 21-day matchday spacing, weekly life events and the ticket price scale are deliberate deviations (see the milestone report).

### What M10 added
- `uv run league --seasons N`: seasons back to back with the rollover (awards, retirements, renewals, progression, intake, squads, next season) the day after each season ends.
- `league/`: `development`, `progression`, `training`, `retirement`, `youth`, `squad`, `awards`, `club_year`, `rollover*`, `health`; `domain/prospects` (request/factory contract) with `seed/prospects`; `verify` L04/L05; `development.yaml`.
- Known: the economy diverged slowly before M11 (rich clubs hoard, small clubs overdrawn).

### What M11 added
- `uv run league --seasons N`: contract talks at the rollover, expiry, summer and mid-season windows with needs, noisy scouting, negotiated fees, medicals, listings, an outside-world club, a final-day squad fill; `verify` L06; `transfer.yaml`. Add `--transfers` to print every completed deal (the market always runs).
- Known: money is closed (outside fees are mirrored legs) but the rich/poor gap is only narrowed, not closed.

### Track B caveats
- `WorldRng` stands in for track A's `SimRng` (same interface); unify when both tracks merge.
- The fast gate took 63-90 s on the dev machine in the Join session (budget 60 s): over budget, profile before M8 adds tests; `--tier pr` about 2 min.
