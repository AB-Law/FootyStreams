# 06 — Milestones and Test Plan

Status: **PROPOSED (Phase 1, revision 4: adds the long-running runtime engine, extensible tactics, voice/TTS design, agent rules + end-of-turn gate, git workflow and PR slicing).** Fifteen milestones (M0–M14), each delivered as a **sequence of small PRs** (see "PR slices" at the end).

**Quality gate at the end of every milestone (non-negotiable):**
1. `uv run check --tier pr` green (static analysis, architecture, unit, property, contract, integration, e2e relevant so far, golden, fast statistical, perf budgets) — see 10 §2.
2. The milestone's CLI command(s) run and their output is reported.
3. New code meets 11 (clean-code limits are lint-enforced; SOLID/DRY checked against the 11 §10 checklist); new invariants are added **to `verify/`**, not to tests.
4. Perf: benchmark table vs. budgets (11 §6) in the report; no regression > 15% vs. previous milestone.
5. Changelog fragments added; design docs updated; `docs/milestones/Mx.md` written; `docs/status.md` refreshed.
6. Coverage floor (≥ 90% branch overall; 100% on listed critical modules from the milestone they appear).
7. Delivered as **one branch and one PR for the whole milestone** (11 §12), built from atomic Conventional Commits of ≤ 400 changed lines each (the slice list below is the commit plan); the PR description has one section per slice; the end-of-turn Stop-hook gate (`uv run check`) was green for every turn; **the milestone stopped at the human review checkpoint and was pushed and PR'd only after your explicit go-ahead.**

Sizes: S ≈ half a day, M ≈ 1–2 days, L ≈ 3+ days of focused work.

| # | Milestone | Size | What runs at the end |
|---|-----------|------|----------------------|
| M0 | Project scaffold & quality gates | S | `uv run pytest` (smoke), `ruff`, `mypy` all green; `uv run sim --help` prints |
| M1 | Domain models + schema export | M | `uv run export-schemas` writes `schemas/`; round-trip & property tests green |
| M2 | Static data + world generator | L | `uv run seed --seed 1` writes `data/worlds/seed-1/`; `--validate` passes; byte-reproducible |
| M3 | Persistence (repos, SQLite, Alembic) | M | `uv run seed --seed 1 --db league.sqlite`; repository round-trip tests; `alembic check` clean |
| M4 | Sim kernel v0: open-play chain | L | `uv run sim --home KES --away HAR --seed 7` prints a goal-scoring play-by-play and summary |
| M5 | Dead balls, discipline, referee | M | Same command now shows fouls, cards, offsides, corners, throw-ins, penalties, added time |
| M6 | Fatigue, injuries, weather, home advantage, AI manager | L | Substitutions and tactical changes appear; invariants suite green |
| M7 | Summary, ratings, context/momentum, analytics-ready stats, `frame` events, full event schema | M | Summary table + ratings in CLI; `--frames` emits tracking snapshots; every event validates; schemas final |
| M8 | Balance harness, profiles, sensitivity & fit | L | `uv run balance --profile realistic --matches 1200` prints the targets table, all PASS; `balance sensitivity` prints the knob × metric matrix |
| M9 | League layer: schedule, standings, post-match, finance, daily tick, **mood & world events** | L | `uv run league --seed 1` plays a 56-match season day by day, prints standings; finance invariants hold; a match shows a "difficult week" storyline and its effect |
| M10 | **Player development, retirement, youth intake, season rollover** | L | `uv run league --seasons 5` rolls seasons; age-curve and economy checks print |
| M11 | **Contracts and transfers** (windows, AI clubs, OUTSIDE_WORLD market) | L | `uv run league --seasons 5` now includes transfer windows; `uv run league transfers --season 2` lists deals; closed-system ledger holds |
| M12 | **Runtime engine** (13): the long-running service | L | `uv run engine --pace scaled:200 --sink ndjson:stdout` streams a continuous broadcast feed (matches, segments) forever; SIGTERM + restart resumes mid-match; `--pace instant --max-seasons 1` = `uv run league` |
| M13 | Video review (optional), extension Protocols/stubs, voice contract | M | Plumbing demo (events → `EchoNarrator` → `NullVoice`) running inside the engine; broadcast-rehearsal e2e (E5) green |
| M14 | **Hardening, soak, chaos, release gate**; README; container | L | `uv run check --tier nightly` and `--tier release` green (50- and 200-season soak, fuzz 20k setups, mutation ≥ 85%, crash-recovery, quarantine/fallback, shadow run); Dockerfile + restart policy; README + release notes v0.1.0 |

(Persistence M3 precedes the sim so the CLI `--home/--away` resolve from a real world; `sim` can also load straight from the world JSON with `--world`.)

## Parallel tracks (optional, after M1 is merged)

The match engine can be built by a second agent in parallel with the rest of the world, because the two sides only meet at the contracts frozen in **M1** (`MatchSetup`, `TeamSheet`, `PlayerSnapshot`, the event union, `MatchSummary`, `MatchResult`). Each milestone is still **one branch and one PR** (11 section 12), the owner reviews each at its checkpoint, and at most one PR per track is open at a time.

| Track | Milestones (in order) | Owns (packages and files) |
|-------|------------------------|---------------------------|
| **A. Match engine** | **M4** sim kernel → **M5** dead balls and discipline → **M6** fatigue, injuries, weather, AI manager → **M7** summary, ratings, frames | `sim/`, match checks in `verify/`, `tests/unit/sim`, `tests/golden`, `tests/statistical` |
| **B. World** | **M2** seed and static data → **M3** persistence → **M9** league layer → **M10** development and rollover → **M11** contracts and transfers | `seed/`, `persistence/`, `league/`, world checks in `verify/`, `data/` |
| **Join** | **M8** balance (needs A through M7 and B's M2) → **M12** engine (needs both) → **M13** → **M14** | `tools/balance`, `runtime/`, `extensions/` |

Track A's milestones stay sequential: M5, M6 and M7 all edit the same simulation state, decision and emit code.

**What changes in the plan to make the tracks independent**
- **M4 no longer builds `league.setup.build_match_setup` or the lineup AI.** They move to M9 (track B). Track A's tests build setups with `tests/factories` (`make_setup`, `make_team_sheet`, `make_player`).
- **M4's `sim` CLI** runs on factory teams (`uv run sim --demo --seed 7`) until a world exists; loading `--home/--away` from a world (`--world` / `--db`) is a small integration commit made by whichever track merges second.
- **M9 does not wait for the real simulator.** The league layer depends on a `MatchSimulator` Protocol with two implementations: `ResultOnlySimulator` (deterministic score from team ratings, no events; built in M9, and the same fallback the production quarantine path needs, 10 section 7) and `EventSimulator` (wraps `simulate_match`, wired in at M12 or earlier). M9's season-level acceptance runs on `ResultOnlySimulator` until A is merged, then once more on the real one.
- **M8 needs both:** statistical runs use the generated league (M2) and the full sim (M7); its calibration is the first end-to-end proof that the tracks fit together.

**Rules for working in parallel**
1. Start only after M1 is merged. Each agent works in its own **git worktree** and branch (`feat/m4-sim-kernel`, `feat/m2-seed-world`); never both in one checkout.
2. A change to a frozen M1 contract (models, events, schemas) is a tiny separate PR with a schema version bump, merged first; both tracks then merge `main`.
3. Shared files and how to keep conflicts small: `uv.lock` and `pyproject.toml` (each track adds only its own dependencies; regenerate the lock after merging `main`), `CHANGELOG.md` (generated: re-run `uv run changelog build`), `docs/status.md` (one section per track), `verify/` (match and world checks live in separate modules; `__init__` exports are merged by hand), `tests/factories` (M1 owns the core builders; tracks add new modules, never edit others').
4. **Changelog fragment ids can collide** when two branches both take the next number. Until `changelog check` detects duplicate ids (a small tooling follow-up to make before starting parallel work), the track that merges second renumbers its fragments after merging `main`.
5. After both tracks have merged, run the integration checks: `sim` from a generated world, `league` on `EventSimulator`, determinism of a season, and the M8 statistical tier.

---

## M0 — Scaffold and test/quality infrastructure
**Do:** `git init`, add the remote `https://github.com/AB-Law/FootyStreams` (empty, public), commit the reviewed design baseline locally; **after your review and explicit go-ahead**, push it as `main` (the bootstrap push) — then everything else follows the PR workflow with a review checkpoint per slice; list branch-protection settings and CODEOWNERS for you to apply (needs admin rights); `uv init` (src layout, Python ≥ 3.12), pin tooling; **make the end-of-turn gate real** (`uv run check` replaces the no-op; unit tests for `tools/hooks/gate.py`); PR template, `pr-size` and `commit-msg` checks; `pyproject.toml` (ruff with the 11 §2 rule set, mypy strict + pydantic plugin, pytest markers/plugins, script entries); empty packages per 04 §2; typer stubs for the commands; **`uv run check [--tier]`** runner; **architecture tests** (import matrix, banned imports/ops in `sim`, module-size limit); `tests/factories` + `tests/helpers` skeletons; hypothesis profiles; coverage config with per-module floors; `pytest-randomly/timeout/socket`; benchmark harness skeleton and `tests/performance` budget file; **`changelog` tool (`new`, `check`, `build`, `release`) with tests**; `golden` tool skeleton; `verify/` package skeleton with the `Violation` type; CI workflow (Windows + Linux, Python 3.12/3.13, uv cache, artifacts) and pre-commit config; `.gitignore`; `docs/status.md`, `docs/glossary.md`, `docs/adr/0001-*.md` (restricted-math determinism), `0002` (JSON-document persistence).
**Tests:** smoke import; architecture tests pass on the empty skeleton; `--help` for each command; changelog tool unit tests (fragment parsing/validation, build output, check rules with a fake diff); `uv run check` exits 0; a deliberately failing fixture proves each gate can fail (a "gate canary" test that the lint/coverage/architecture checks actually catch violations).

## M1 — Domain models and schema export
**Do:** all models in 01 (types, Person, Player + attrs, Manager, Staff, Referee, MediaPersonality, Club/Stadium/Fanbase/Finance/Facilities/Board/Academy, TeamTactics, Competition/Season/Fixture/Standings, Match/TeamSheet/PlayerSnapshot/Weather, Relationship, MemoryRecord, Proposal, **StateModifier, WorldEvent, ResolvedMood, transfer/contract entities, TrainingPlan/DevelopmentEntry**), `__usage__` registry, `ratings.compute_current_ability`, `valuation.market_value`, `team_rating`; the **events package** (base, context, all event classes, union, summary) as models only; **`MatchResult` and the test factories both tracks rely on (`make_player`, `make_team_sheet`, `make_setup`, `make_match_result`)**; `export-schemas` + drift test; canonical JSON helper.
**Tests:** unit (validators, ranges), **hypothesis** property tests (random valid models round-trip `model_dump_json → model_validate_json` identically; invalid ranges rejected; age/BMI/competence rules), usage-registry test (no untagged field), schema export/drift test, union discrimination test (every event type parses back to its own class; unknown `type` rejected).

## M2 — Static data and world generator
**Do:** `data/static/*.yaml` (formations, roles, traits, injuries, cultures, archetypes, climate, denylist, default sim config skeleton); `seed/` generators per 05; `world_io` canonical writer/reader; coherence validator; `seed` CLI.
**Tests:** determinism (same seed ⇒ same `content_sha256`; different seed ⇒ different), coherence checks (05 §5), name-quality tests (uniqueness, denylist, n-gram distinctness, culture quotas), archetype strength bands, wage-bill bounds, formation-coverage property test over 20 seeds, committed `default` world matches regeneration.

## M3 — Persistence
**Do:** SQLAlchemy 2.x tables (04 §4), codec, repositories, `UnitOfWork`, in-memory implementations, Alembic init + `0001_initial`, `seed --db`, `WorldReader`.
**Tests:** repository contract tests **parametrised over both implementations** (in-memory and SQLite) — the same suite asserts identical behaviour; optimistic-concurrency (`rev`) conflict test; Alembic upgrade/check/downgrade; "load world into DB and read it back equals the JSON world" test; FK integrity; ledger append-only.

## M4 — Sim kernel v0
**Do:** `SimRng`, `mathx`, `SimConfig`, geometry/positioning/pressure, decision model, pass/dribble/tackle/interception/shot/save/goal, kickoff/halftime/fulltime, match clock, minimal emit (valid events), text renderer, `sim` CLI (`--demo --seed [--format text|ndjson] [--verbosity key|full]` on factory teams; `--home --away [--world|--db]` once a world exists, see Parallel tracks). `build_match_setup` and `lineup_ai` are built in M9.
**Tests:** **determinism** (same inputs ⇒ identical NDJSON bytes; different seed ⇒ different), golden digest for 3 pairings, event validation of the whole stream, invariants: score = goals, no player on both teams, minutes non-decreasing, `seq` contiguous, positions in [0,1], sim package has no banned imports/ops (AST), ≥ 1 match produces plausible shot/goal counts (loose sanity), performance guard (< 0.5 s/match as a tripwire; budget 150 ms mean tightened as the sim grows). **`verify_match` is introduced here** (M01–M05, M10, M17) and extended each milestone (M5: M11–M12; M6: M06–M09; M7: M13–M16, M18); `verify_world` arrives in M3/M9. Sim fuzz (generated valid setups ⇒ totality) starts here with 200 setups and grows each milestone.

## M5 — Dead balls, discipline, referee
**Do:** fouls, cards, advantage, offsides, corners (with aerial resolution), throw-ins, goal kicks, free kicks (direct/cross), penalties, referee model, added time.
**Tests:** sequencing rules (03 §4); red-carded players never appear afterwards; ≤ 11 players, men counts consistent; second-yellow logic; referee sensitivity tests (strict ref ⇒ more fouls/cards over 200 matches); penalty conversion band; offside lines valid; uncalled/advantage branches reachable (coverage of event types by a 300-match sweep — every emitted type appears at least once).

## M6 — Fatigue, injuries, weather, home advantage, AI manager
**Do:** `M_state` (consume `PlayerSnapshot.mood`), exhaustion model, injury hazard & severity, substitution/tactical AI (checkpoints, options, cooldowns), weather & pitch effects, home-advantage channels, half-time talk.
**Tests:** **fatigue non-decreasing within a half** (only the declared halftime recovery decreases it); substituted/injured players generate no later events; sub count ≤ 5, windows ≤ 3 (+HT), GK-bench rule; tactical changes emit structured `reason`; red card triggers a reshape within N minutes in most cases; metamorphic tests (neutral venue ⇒ home edge ↓; heavy rain ⇒ pass accuracy ↓; heat ⇒ more late fatigue; trailing ⇒ more shots after 60′).

## M7 — Summary, ratings, context, event completeness
**Do:** `ctx` computation (momentum, intensity, significance, tags), `match_summary` (team/player stats, ratings, POTM, hooks, timelines, digest, **pass matrix, zone pass flow, shot map, xG/xA/xT totals**), opt-in **`frame` events** (22-player + ball tracking snapshots, `--frames`, default 1 s cadence, deterministic interpolation; invariant test: frames on/off yield identical non-frame events), a read-only `analytics/` module that recomputes those maps from the log, `annotate()` (non-causal), all remaining event fields, schema finalisation, `render` polish.
**Tests:** ratings in [3,10], sum of player stats equals team stats, stats derivable from events (recompute from the log = summary), tags causal (a tagging test replays the stream with a "future-blind" tagger and asserts identical `ctx.tags`), `late_game`/`equaliser`/`go_ahead_goal` correctness on hand-built synthetic logs, schema drift test.

## M8 — Balance harness and calibration
**Do:** `balance` tool (multiprocessing, numpy), `balance_targets.yaml` with profiles (`realistic`, `high_scoring`, `defensive_grind`, `chaos`), the target table in 02 §14, `balance sensitivity` (knob × metric matrix), `balance fit` (optimiser; writes a candidate config), loss function, calibrated `sim_config.default.yaml`, golden digests re-pinned, performance profiling and optimisation pass.
**Tests:** **statistical tier** (`@pytest.mark.slow @pytest.mark.statistical`, ≥ 1,200 seeded matches across all league pairings, both venues, plus stress gaps): goals/match, home/draw/away split, favourite win rate by gap bin (monotone), upset rate bounds, card/foul/injury/penalty/corner/offside rates, goal timing, scoreline distribution; plus a fast tier (200 matches, wide bands) in default CI; metamorphic suite (02 §14.4).

## M9 — League layer (+ daily tick, mood, world events)
**Do:** `schedule` (circle method + home/away balancing), `calendar`, `attendance`, `weather_gen`, `standings` (all tie-breakers), `build_match_setup` and `lineup_ai` (availability: injuries, suspensions, fatigue rotation), the `MatchSimulator` Protocol with `ResultOnlySimulator` (deterministic score from team ratings; also the production fallback) and an `EventSimulator` adapter, `post_match.derive_world_delta`, `finance` (matchday revenue, weekly wage accrual, sponsorship/broadcast instalments, prize money, ledger), `WorldClock` + daily tick pipeline (07 §2), **`mood.resolve_mood`, rule-based `StateModifier`s from facts, the seeded `WorldEventGenerator`, `WorldEvent` feed, public storylines in the kickoff preamble**, `SeasonRunner`, `league` CLI (`--seed`, `--world|--db`, `--matchday N`, `--season-only`).
**Mood tests (added):** `resolve_mood` purity and hard-cap clamps (hypothesis: any modifier set stays inside `MoodConfig` caps); private modifiers never appear in events; matched-control test that a starter with a ≥ 0.15 negative mood underperforms (−0.04…−0.10 goal-difference effect) without being decisive; replaying a match from its stored snapshot reproduces the same log even after the modifiers change.
**Tests:** schedule validity (property test over 8–20 teams); standings tie-break unit tests with hand-computed tables; **finances balance** (`balance == opening + Σ ledger` per club; league-wide closed-system transfers net to zero; income/expense categories reconcile to the season P&L); post-match updates: fatigue/sharpness/minutes consistent with events, suspensions after reds/5th yellow, injuries recorded with return dates, stats increments equal summary; **season replay determinism** (two runs ⇒ identical standings and ledger hash); a 20-season statistical check (02 §14.3); persistence round-trip of a whole season; memory tables remain empty (no memory logic yet).

## M10 — Player development, retirement, youth intake, season rollover
**Do:** `development.yaml` (age curves per attribute group, retirement hazard), weekly training micro-steps and season-end progression (07 §4), PA revision, position-competence/role-familiarity growth, retirement, youth intake + promotion, season rollover steps (07 §7), awards/`WorldEvent`s, history/reputation/fanbase updates, finance rollover; `league --seasons N`.
**Tests:** `CA ≤ PA` always; age-curve shape tests (peak ages per group); league-average CA drift within ±1.5 over 20 seasons; retirement rate 5–9%/season; squad sizes stay 22–28 (after youth promotion); determinism of a multi-season run (hash of standings + ledger + squads); development journal explains every attribute delta; development is independent of the match sim streams.

## M11 — Contracts and transfers
**Do:** `transfer.yaml`; contract renewal/expiry, `TransferWindow`/`Listing`/`Bid`/`ContractOffer`/`Transfer` flow, AI needs analysis, noisy scouting (perceived ability), valuation/negotiation (≤ 3 rounds), medicals, sales logic (surplus/unhappy/financial), the synthetic `OUTSIDE_WORLD` market, deadline panic-buying, mood side-effects, ledger legs, `league transfers` report.
**Tests:** transfer atomicity (inject failure ⇒ no partial state); closed-system ledger identity with declared external accounts and per-transfer leg symmetry; squad invariants at window close (≥ 22 senior, ≥ 2 GK, every formation slot coverable); fee/market-value ratio and transfers-per-window bands (07 §8); AI never exceeds budget; scouting noise shrinks with `judging_ability`; 20-season economy stays in band; determinism.

## M12 — Runtime engine (the long-running service; design in 13)
**Do:** `runtime/` package: `Clock` (system/scaled/virtual), `EngineConfig`, `Supervisor` (restart/backoff, graceful shutdown, single-instance lock), `WorldDriver`, `SimulationBuffer` (process-pool pre-simulation + verify + quarantine hook), `BroadcastScheduler` (programme blocks, filler), `MatchPlayer` (paced replay, playback cursor), `EventBus` + sinks (NDJSON stdout/file, in-memory), `HealthReporter`; `BroadcastEvent` schema (`schemas/broadcast.schema.json`); `uv run engine`; `uv run league` re-expressed as the engine in `instant` mode.
**Tests:** virtual-clock tests (a season in seconds), pacing accuracy, buffer starvation → filler, sink isolation (slow/raising sinks), crash/restart resumes at the cursor with no duplicates, graceful SIGTERM, single-instance lock, clock-skew handling, no wall-clock usage outside `runtime/` (architecture test), **E12**: start the real process, read NDJSON for an accelerated matchday, SIGTERM, restart, verify continuity.

## M13 — Video review (optional), extension seams, voice contract
**Do:** `review` (goal/penalty/red-card checks with overturn rates linked to referee `consistency`/`video_reliance`; sequencing rules in 03 §4); `extensions/` Protocols, types and stubs (`Narrator`, `MemoryUpdater`, `VoiceSynthesizer v2` with `VoiceProfile v2`/`SpeechRequest`/`SynthCapabilities`, `ManagerPolicy`), `NullVoice`/`EchoNarrator` plugged into the engine as optional sinks with timeouts and bounded queues; re-run balance (review shifts goal counts slightly).
**Tests:** review invariants (score reconstruction with overturns, under_review sequencing); Protocol conformance tests for stubs (shared contract suite); **E5 broadcast rehearsal** including slow/raising/disconnecting consumers (ordering preserved, nothing lost, core never blocked).

## M14 — Hardening, soak, chaos, release gate
**Do:** Dockerfile + compose with restart policy and volume for the DB; `quarantine` + fallback-profile retry + result-only fallback in the engine/league runner (10 §7), `uv run health`, `uv run verify --db`, `--safe-mode`, backup-before-migrate, crash-recovery idempotency polish; soak runner (50- and 200-season), fuzz harness (generated degenerate setups/worlds), fault injectors (DB failure mid-transaction, process kill, corrupt row), mutation-testing job and surviving-mutant triage, cross-version DB fixtures (E7), shadow-run script (7 virtual days), perf baseline on the pinned runner, README (setup, commands, schema layout, how Narrator/MemoryUpdater/VoiceSynthesizer/ManagerPolicy plug in, determinism contract, calibration and tuning howto, operations runbook), `release-notes/v0.1.0.{md,json}` via `changelog release`.
**Tests:** all of T2 and T3 (10 §2) green; E1–E11 green; docs tests (README commands execute); mutation score ≥ 85% on critical modules; 200-season run: no invariant violations, memory/DB growth within bounds, no performance drift; chaos suite (kill/restore, injected failures ⇒ no partial state, resume equals uninterrupted run).

---

## Commit plan per milestone (one branch and one PR per milestone)

A milestone is **one branch (`<type>/<milestone>-<slug>`) and one PR**. Each slice below becomes one or more **atomic commits** of ≤ 400 changed lines each (generated files excluded); every commit builds, passes `uv run check`, and carries its own tests. Each slice also contributes a changelog fragment and a section of the PR description. The list is an *initial plan*: split a slice into more commits whenever a commit grows (11 §12).

| Milestone | Slices (in order) |
|-----------|-------------------|
| **M0** | 1 uv project + pyproject + empty packages · 2 ruff/mypy/pytest config + smoke test · 3 `check` runner + hypothesis/coverage/random-order plugins · 4 architecture tests + gate-canary test · 5 test factories/helpers skeleton · 6 `changelog` tool (`new`, parse/validate) · 7 `changelog check/build/release` · 8 gate hook tests · 9 PR template, `pr-size`, `commit-msg`, pre-commit · 10 CI workflow · 11 ADRs, glossary, `docs/status.md` |
| **M1** | 1 primitive types + ids + enums · 2 Person/Personality/Appearance · 3 attributes + Player core · 4 contract/injury/condition models · 5 `PlayerProfile` + `ratings` + `valuation` · 6 Manager/Staff/Referee · 7 Club/Stadium/Fanbase/Finance/Board · 8 `TeamTactics` core + module registry + v1 modules · 9 Competition/Season/Fixture/Standings · 10 Match/TeamSheet/PlayerSnapshot/Weather · 11 Relationship/Memory/Proposal/StateModifier/WorldEvent/transfer models · 12 media/voice models · 13 event base/context + event types (3 PRs by family) · 14 summary models · 15 usage registry + schema export + drift test |
| **M2** | 1 static YAML loaders + validation · 2 name cultures + generator + quality gates · 3 player generator (archetypes, spiky profiles) · 4 manager/staff generators · 5 club/stadium/finance generators · 6 referee + media generators · 7 relationships · 8 coherence validator · 9 world IO + `seed` CLI + committed default world |
| **M3** | 1 ports + in-memory repos · 2 repository contract suite · 3 SQLAlchemy tables + codec · 4 generic JSON-document repo + concrete repos · 5 UnitOfWork + transactions · 6 Alembic + migration tests · 7 `seed --db`, `WorldReader`, `verify_world` skeleton |
| **M4** | 1 `SimRng` + `mathx` (+ determinism/banned-ops tests) · 2 `SimConfig` + tables · 3 geometry + positioning · 4 pressure + decision model · 5 pass/dribble/tackle resolution · 6 shot/save/goal · 7 clock/state/emit · 8 `simulate_match` API (setups come from factories) · 9 text renderer + `sim` CLI · 10 `verify_match` v1 + goldens + sim fuzz |
| **M5–M8** | One PR per behaviour area (e.g. M5: fouls · cards/referee · offside · corners/throw-ins/goal kicks · free kicks · penalties · added time), each with tests and a verify extension; M8: harness · profiles/targets · sensitivity · fit · calibration commit (config + goldens as separate commits) |
| **M9** | `MatchSimulator` + `ResultOnlySimulator` · `build_match_setup` + lineup AI · schedule · standings · attendance/weather · finance/ledger · post-match deltas · mood resolver · rule-based modifiers · world-event generator · daily tick pipeline · season runner + `league` CLI |
| **M10** | development.yaml + curves · weekly micro-steps · season progression · retirement · youth intake · rollover · economy checks |
| **M11** | contracts/renewals · windows + listings · needs analysis · scouting noise · bids/negotiation · player terms + medicals · sales logic · OUTSIDE_WORLD market · completion + ledger legs · reports |
| **M12** | Clock + config · supervisor + lock · sim buffer · scheduler/programme · match player + cursor · bus + sinks · health · `engine` CLI + E12 |
| **M13** | review model + sequencing · review in sim · extension Protocols + stubs · voice contract · engine integration |
| **M14** | quarantine/fallback · verify/health CLIs · safe mode · soak runner · fuzz harness · fault injectors · mutation job · shadow run · Dockerfile · README · release notes |

Rules of thumb: tests + implementation + docs for a slice ship together; golden/schema/data regenerations are separate commits in the same PR. (M0 was delivered before this rule, as 13 PRs; from M1 on it is one PR per milestone.)

## Test plan (cross-cutting) — summary only

> The authoritative test strategy is **10-testing-strategy.md** (17 test types, tiers T0–T3, 11 end-to-end scenarios, edge-case catalogue, invariant catalogue, mutation/performance/chaos/soak testing, operational safety for the live channel). The table below is a quick index and must not diverge from it.

| Layer | Tool | What it proves |
|-------|------|----------------|
| Unit | pytest | Validators, formulas, RNG streams, tie-breakers, ratings |
| Property | hypothesis | Model round-trips and invalid-input rejection; schedule validity for any team count; `squash` bounds/monotonicity; RNG forking independence; name-gate rules |
| Invariants (run on every sampled match, `--strict`) | pytest | **Score equals goal events (with review outcomes); no player on both teams; ≤ 11 on pitch and ≥ 7; red-carded and substituted players produce no later events; minutes/`t`/`seq` monotone; fatigue non-decreasing within play; subs ≤ limit; every event validates; positions within [0,1]; ids unique; sequencing rules** |
| Determinism | pytest | Same seed ⇒ identical bytes (in-process, across processes, `PYTHONHASHSEED` varied, on Windows & Linux CI); stream isolation (the `play` stream's draw sequence is identical across runs that differ only in injury/discipline/manager config, verified by comparing recorded draw counters per stream) |
| Golden | pytest | Pinned `log_digest` for fixed (pairing, seed, config); regenerated intentionally with a documented command when `SIM_VERSION` bumps |
| Statistical | pytest (slow) + `balance` | 02 §14 targets |
| Persistence | pytest | Repository contract parity (memory vs SQLite), migrations, optimistic concurrency, finance ledger invariant, atomic match commit (inject a failure mid-transaction ⇒ nothing persisted) |
| Architecture | pytest AST | Import matrix, banned modules/ops inside `sim` |
| Schema | pytest | Drift test; union discrimination; JSON Schema validates sampled real events (via `jsonschema` in dev deps) — the cross-language contract is verified against actual output |
| CLI | pytest (typer runner) | `sim`, `league`, `seed` exit codes and key output lines |

**Definition of done per milestone:** the six-point quality gate at the top of this file.
