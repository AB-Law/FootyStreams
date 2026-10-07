# 10 — Testing Strategy and Operational Safety

Status: **PROPOSED (revision 3).** Premise: the league will run as a 24/7 channel. A crash, a corrupted match, an impossible score or a stalled schedule is **a visible failure on air**. So the strategy has two halves: (A) a layered test suite that makes regressions very hard to merge, and (B) *runtime* safety design so that even an unforeseen bug cannot reach the audience unverified.

## 0. Principles

1. **One implementation of every invariant, used everywhere.** Invariants live in `footystreams/verify/` (pure functions returning `Violation`s). Unit tests, property tests, the soak runner, the `--strict` CLI flag **and the production pre-air gate** all call the same code (DRY). A test never re-implements a rule; it calls the verifier.
2. **Totality for valid input.** For any *valid* `MatchSetup`, `simulate_match` must terminate, never raise, and satisfy all match invariants. Invalid setups are rejected up front by Pydantic validators (`InvalidSetupError`) — never mid-match. Edge cases that can legally happen (GK sent off with no spare keeper, a team reduced below 7, all bench injured) have *defined rules* (§4) rather than undefined behaviour.
3. **Determinism makes bugs reproducible.** Every failure is a `(seed, setup/config hash)` pair; every failing property or soak run prints a one-line repro command. Every fixed bug adds a permanent regression test.
4. **No flaky tests, ever.** Randomness only from explicit seeds; no wall-clock or network in tests (`pytest-socket` blocks network; the sim package has no I/O by construction); tests run in random order (`pytest-randomly`, seed printed) to expose order dependence; there is **no retry plugin** — a flaky test fails the build until fixed.
5. **Fast feedback first.** The fast tier runs on every save/commit in < 60 s; heavier tiers run on PR/nightly/weekly (§2).
6. **Tests are code too:** same clean-code rules (11), builders instead of copy-paste fixtures, descriptive names, no logic in tests.

## 1. Test types (what, where, how)

| # | Type | Tool | Location | Proves |
|---|------|------|----------|--------|
| 1 | **Static analysis** | ruff (incl. complexity & magic-number rules), mypy `--strict`, `vulture` (dead code), `pip-audit`, duplicate-code check | CI/pre-commit | Style, types, no dead code, no copy-paste, no known-vulnerable deps |
| 2 | **Architecture** | AST tests (import matrix, banned modules/ops in `sim`, no cycles, module-size limits) | `tests/architecture/` | The layering/SOLID boundaries (11 §3) cannot erode |
| 3 | **Unit** | pytest | `tests/unit/` mirroring `src/` | Pure functions: formulas, tie-breakers, ratings, valuation, mood resolution, name gates, RNG |
| 4 | **Property-based** | hypothesis | `tests/property/` | Model round-trips; validators; `squash` bounds/monotonicity; schedules valid for any team count; RNG fork independence; ledger identities; mood caps for any modifier set; **sim totality + invariants over generated setups** |
| 5 | **Metamorphic** | hypothesis/pytest | `tests/metamorphic/` | Relations without an oracle: neutral venue lowers home edge; +5 to all attributes raises win rate; red card lowers expected points; frames on/off ⇒ identical non-frame events; swapping team order + venue mirrors results statistically |
| 6 | **Contract** | pytest, shared contract suites | `tests/contracts/` | Every `Repository` implementation (memory, SQLite) passes the *same* suite (LSP); every sim component implementation passes the component contract; stubs satisfy extension Protocols; JSON Schema (checked by independent `jsonschema` library) validates real events/models |
| 7 | **Integration** | pytest | `tests/integration/` | Sim ↔ league ↔ persistence on SQLite; migrations; transactions/rollback; post-match deltas; transfers atomicity |
| 8 | **End-to-end** | pytest + subprocess | `tests/e2e/` | Real CLI commands, real files, real SQLite, whole-season/multi-season flows (§3) |
| 9 | **Golden / regression** | pytest | `tests/golden/`, `tests/regressions/` | Pinned digests; pinned CLI text output; every past bug stays fixed |
| 10 | **Determinism** | pytest + CI matrix | `tests/determinism/` | Same bytes in-process, across processes, `PYTHONHASHSEED` values, Windows/Linux, Python 3.12/3.13; replay from DB reproduces the log |
| 11 | **Statistical / balance** | numpy harness | `tests/statistical/` (marker `statistical`) | Balance targets (02 §14), strength-gap monotonicity, season/parity, economy, development curves |
| 12 | **Performance** | pytest-benchmark + op-count assertions | `tests/performance/` | Budgets (11 §6) and no regressions (§6 below) |
| 13 | **Soak / endurance** | runner script + pytest | `tests/soak/` (marker `soak`) | 50–200 seasons: no exceptions, invariants hold every tick, memory/DB growth bounded, no performance drift |
| 14 | **Fuzz & chaos / fault injection** | hypothesis, custom injectors | `tests/chaos/` | Degenerate worlds; DB failures mid-transaction; process kill mid-tick ⇒ clean recovery; corrupted rows ⇒ clear error |
| 15 | **Mutation** | mutmut (Linux CI) | nightly job | The tests actually detect bugs in the critical modules (§5) |
| 16 | **Documentation tests** | pytest | `tests/docs/` | README/CLI examples run; every design-doc code block marked `python` parses; usage registry (S/L/R) complete; changelog check |
| 17 | **Broadcast rehearsal** (E5) | pytest | `tests/e2e/` | The future live pipeline contract: paced event feed → narrator stub → voice stub → sink, with failures injected (§3, E5) |

## 2. Tiers, budgets and when they run

| Tier | Runs | Contains | Budget |
|------|------|----------|--------|
| **T0 fast** | **end of every agent turn (Stop hook, 11 §11)** / every commit / pre-commit / `uv run check` | static analysis, architecture, unit, property (small `max_examples`), contract, ≈ 30-match smoke sim + invariants, golden digests (5), rules-sync check, changelog check; **passes 100% or the agent's turn is not allowed to end** | **≤ 60 s** (xdist) |
| **T1 PR** | every pull request | T0 + integration + full property (100 examples) + metamorphic + e2e E1–E4, E8, E10 + sim fuzz (500 setups) + 200-match fast statistical + 3-season soak + perf gates | **≤ 10 min** on CI (Windows + Linux matrix, Python 3.12 & 3.13) |
| **T2 nightly** | scheduled | 1,200-match statistical (all profiles), sim fuzz 20,000 setups, 50-season soak, e2e all (E1–E10), mutation testing on critical modules, perf benchmarks vs baseline on a pinned runner, `pip-audit` | ≤ 90 min |
| **T3 weekly / release gate** | scheduled + before any release | 200-season parity/economy run, cross-version DB migration, 7-virtual-day **shadow run** (§7), full determinism matrix incl. macOS, long hypothesis (2,000 examples) | ≤ 6 h |

Commands: `uv run check` (T0), `uv run check --tier pr` (T1), `uv run check --tier nightly`, `uv run check --tier release`. Hypothesis profiles: `dev` (20 examples), `ci` (100), `nightly` (2,000), selected by env var; failing examples are saved and converted into regression tests (policy below).

**Coverage gates:** overall branch coverage ≥ 90%; **100% line + branch** for `verify/`, `league/finance.py`, `league/standings.py`, `league/mood.py`, `sim/rng.py`, `sim/mathx.py`, `persistence/uow`; CI fails below. Coverage is a floor, not the goal — mutation testing (§5) checks quality.

## 3. End-to-end scenarios

All E2E tests run the real CLI (or the real **engine** process) as a subprocess in a temporary working directory (no mocks), then assert on exit code, stdout key lines, files, and database content (read back through the repository layer *and* raw SQL for independence).

| ID | Scenario | Asserts |
|----|----------|---------|
| **E1** | **Fresh-clone flow:** `seed --seed 1` → `sim --home X --away Y --seed 7` → `league --seed 1` in an empty temp dir | Exit 0; world files + manifest hash stable; play-by-play contains kickoff/fulltime/summary; standings table printed with 8 rows; runtime within budget |
| **E2** | **Persisted season:** `seed --db` → `league --db --season-only` → inspect SQLite | 56 matches; every match's events pass `verify_match`; standings recomputed == cached snapshot; ledger identity holds per club; stats = Σ summaries; DB `integrity_check` ok; second run with same seed ⇒ identical world+ledger hash |
| **E3** | **Multi-season (5 seasons):** development, rollover, contracts, transfers, outside-world market | World invariants (W01–W18) at every day boundary; squad rules at window close; economy within band; CA ≤ PA; determinism hash identical across two runs |
| **E4** | **Replay:** load a stored match record, rebuild the sim input from its snapshot, resimulate | Event log digest identical to the stored digest even after the world has moved on (mood, injuries, transfers) |
| **E5** | **Broadcast rehearsal:** replay one matchday through an `EventSink` pipeline at 200× speed with `EchoNarrator` → `NullVoice`; inject a slow narrator (timeouts), a raising narrator, a dropped sink connection | Ordering preserved; no events lost; slow/raising layers are skipped with a logged fallback line and **never** block or alter the event stream; backpressure bounded; pipeline finishes |
| **E6** | **Crash recovery:** run `league` in a subprocess, `terminate()` it at random points (seeded), restart | Resumes at the right day; no duplicate ledger entries/events (idempotent stages via `world_log`); `PRAGMA integrity_check`; final hash equals an uninterrupted run |
| **E7** | **Upgrade path:** open a DB created by the previous release (kept as fixture), run Alembic upgrade, run a season | Data preserved; invariants hold; backup file created before migration |
| **E8** | **Schema contract:** run 50 matches; validate every event and summary against the committed `schemas/*.json` using an independent JSON-Schema validator; verify `schemas/` regenerated == committed | Zero violations; any model change without schema regeneration fails |
| **E9** | **Config/profile run:** custom `--config`, `--profile chaos` | `config_hash` recorded; behaviour changes as intended (e.g. more cards); invariants still hold |
| **E10** | **CLI UX:** unknown club, missing world, bad seed, read-only dir, `--help` | Exit code 2, readable one-line error, no stack trace; help text lists all options |
| **E12** | **Engine (the real long-running service, 13):** start `uv run engine --pace scaled:200 --sink ndjson:stdout` as a subprocess; read the feed for one accelerated matchday; send SIGTERM; restart; kill -9 once mid-match and restart | Continuous `BroadcastEvent` stream; resume at the cursor with no duplicate `(match_id, seq)` and no gap; clean exit code on SIGTERM; health file updated; second instance refused by the lock; stream never stalls when the buffer is starved (filler) |
| **E11** | **Frames:** `sim --frames` | 1 s frame cadence; frames add no RNG draws; non-frame events byte-identical to the frames-off run |

## 4. Edge-case catalogue (each has a named test; rules are defined, not accidental)

| Case | Defined behaviour |
|------|-------------------|
| Goalkeeper injured/sent off, spare GK on bench | Substitution forced if subs remain (an outfield player is removed to make room if the team has used no windows); otherwise see next |
| Goalkeeper sent off, no spare GK or no subs left | Highest `handling + shot_stopping` outfield player becomes the **emergency keeper** (event `tactical_change` with reason `emergency_keeper`); GK stats penalty from low competence |
| A team reduced below 7 players | Match **abandoned**: `fulltime` with `result_reason=abandoned_insufficient_players`, 3–0 awarded; flagged in summary (astronomically rare; tested by forced scenario) |
| Injury and card in the same tick | Ordering rule: foul → card → injury → stoppage; both processed; invariants hold |
| Two substitutions in one stoppage | Allowed within windows; ordering by slot; no duplicate player ids |
| Goal in the last second / stoppage | Clock may exceed scheduled end only through the stoppage mechanism; `fulltime` after next dead ball or max-overrun |
| Penalty awarded after the final whistle window | Played out (rule: ball dead + penalty pending is completed) |
| Formation slot with no competent player after a red card | Nearest-position reassignment by competence; flagged `out_of_position` in lineup changes |
| Identical teams / identical attributes | Works; outcomes still vary via RNG; tie rules unaffected |
| Attributes 1 / 100 extremes, fatigue 1.0, morale 0 | Effective-attribute clamps keep all probabilities inside `[ε, 1−ε]` (property test over the whole attribute space) |
| Zero attendance, capacity 5,000 vs 80,000 | Crowd factor stays in [0,1]; no division by zero |
| Referee extremes (strictness 0/1) | Calls/cards rates monotone, never undefined |
| Weather extremes (−10 °C, 42 °C, 30 mm/h rain) | Modifiers clamped; match completes |
| Venue with `capacity < attendance` | Rejected at setup validation |
| League with an odd number of teams / 2 teams / 20 teams | Scheduler handles (bye or rejection by rule); property test over 2–24 teams |
| Day tick re-run | Idempotent (stage digests in `world_log`) |
| Transfer window with insolvent club | Cannot bid; may be forced to sell; invariants hold |
| Player retired / injured / suspended appears in lineup | Rejected by `build_match_setup`; `lineup_ai` never selects them (invariant W11) |
| Stale `rev` write (concurrent updater) | `ConflictError`, nothing partially applied |
| Corrupt/unknown-version JSON row | `SchemaVersionError` with entity id; migration function exists or clear instruction |

## 5. Mutation testing and test quality

`mutmut` (Linux CI) runs nightly on the critical pure modules: `sim/mathx.py`, `sim/rng.py`, `sim/discipline.py`, `sim/fatigue.py`, `verify/*`, `league/standings.py`, `league/finance.py`, `league/mood.py`, `league/schedule.py`, `domain/ratings.py`. Target mutation score ≥ 85% (surviving mutants are triaged: add a test or document as equivalent). A summary is published as a CI artifact; the score is tracked in the milestone report.

## 6. Performance testing

- **Budgets as tests** (11 §6 table): mean/p95/p99 match time, season time, tick time, DB throughput, memory, CLI start-up. `tests/performance/` uses `pytest-benchmark`; T1 asserts generous budgets (regression tripwires), T2 compares against a stored baseline on a **pinned runner** and fails on > 15% regression in mean or > 25% in p99.
- **Hardware-independent proxies:** because wall-clock varies across machines, tests also assert *operation counts* per match (RNG draws, candidate evaluations, position updates, allocations measured via `tracemalloc` peak) — stable, deterministic, and exactly what regresses when someone writes an accidental O(n²).
- **Profile before optimising:** `uv run profile sim ...` (cProfile + optional py-spy) output saved in the milestone report; any optimisation that costs readability must link the benchmark that justifies it (11 §6).
- **Scaling tests:** matches/second with 1, 4, 8 workers (matchday-parallel simulation); season/transfer-window/tick times as the world grows over 20 seasons (no super-linear growth: history tables are indexed and queries are bounded).

## 7. Operational safety for a live channel (design requirements the tests enforce)

1. **Pre-simulation buffer.** Matches are simulated and persisted *ahead of airtime* (default ≥ 1 matchday ahead; ≥ 2 for the weekend). The live stream only ever **replays verified stored logs**; the sim never runs on the critical path. A sim bug therefore surfaces hours before it could be seen.
2. **Pre-air verification gate.** After simulation, `verify_match(result)` (all M-invariants + full schema validation + digest check + summary-from-events recomputation) runs in production, not just tests. Pass ⇒ fixture `broadcast_ready`. Fail ⇒ fixture `quarantined` (see below).
3. **Quarantine & fallback.** A quarantined match is never aired. The league layer (a) logs a structured incident with `(fixture, seed, sim_version, config_hash, violations)`; (b) retries once on the **conservative fallback profile** (`model_profile` previous stable) *with the same seed*; if that verifies, it is aired and the incident recorded; (c) otherwise the schedule uses a pre-verified filler (an archived classic or highlights) and the world is advanced using a **"result-only" deterministic fallback** (score from the team-strength model, no events) so the league continues. Every branch has an E2E test using fault injection.
4. **Idempotent, atomic stages.** One transaction per match (events + summary + deltas); one per daily-tick stage; every stage recorded in `world_log` with a digest; restarting after a kill resumes exactly (E6).
5. **Migrations are safe.** Automatic DB backup before every upgrade, upgrade tested against previous-release fixtures (E7), restore tested. Never auto-migrate during a live run.
6. **Version pinning.** Each fixture records the `sim_version`/`config_hash` that produced it; unplayed fixtures may move to a new version only at a controlled boundary; played matches are never re-simulated implicitly.
7. **Shadow run before release.** The release gate (T3) runs the candidate against a copy of the production world for **7 virtual days**, comparing balance metrics and invariant violations against the current release (canary comparison). No red metrics ⇒ promote.
8. **Side-layers cannot hurt the core.** Narrator/voice/renderer failures, timeouts and slowness are contained by timeouts, bounded queues and null fallbacks (E5); they have no write path into ground truth.
9. **Health check.** `uv run health --db league.sqlite` verifies DB integrity, schema/sim versions, the buffer depth, quarantined fixtures, last-tick age; exit code non-zero on any problem — ready for a future supervisor.
10. **Kill switch/safe mode.** `SimConfig.safe_mode` (and `--safe-mode`) forces the previous stable profile, disables optional features (reviews, frames) — tested equivalent invariants.

## 8. Test engineering conventions

- **Layout:** `tests/<type>/` mirrors `src/footystreams/`; shared builders in `tests/factories/` (`make_player(**overrides)`, `make_team_sheet`, `make_setup`, `make_world(seed)`), shared assertions in `tests/helpers/` that delegate to `verify/`.
- **Naming:** `test_<unit>__<scenario>__<expected>`; one behaviour per test; AAA structure; parametrise tables instead of loops.
- **Determinism:** `conftest.py` fixes seeds, forbids network (`pytest-socket`), applies timeouts (`pytest-timeout`: 5 s unit, 60 s integration, 15 min soak), and randomises order.
- **Regression policy:** every bug ⇒ failing test first, in `tests/regressions/test_<id>_<slug>.py` referencing the changelog fragment id; every hypothesis failure ⇒ pinned as an explicit example.
- **Golden files:** regenerated only with `uv run golden update` which refuses to run unless `SIM_VERSION` was bumped and a changelog fragment declares `sim_version_impact`; diffs are human-reviewable.
- **Test data:** worlds generated by the real generator from fixed seeds, plus a few hand-built minimal worlds (2 teams) for readable scenarios.
- **No mocks of our own domain objects;** fakes only at the edges (clock-free, network-free), preferring the in-memory repository to mocks.

## 9. Invariant catalogue (implemented once in `verify/`)

Match (`verify_match`): M01 `seq` contiguous from 0 · M02 `t` non-decreasing, within period bounds · M03 ids unique · M04 score = confirmed goals (review-aware) · M05 no player on both teams · M06 ≤ 11 on pitch, GK present or emergency keeper · M07 sent-off/subbed-off/injured-off players never reappear · M08 subs ≤ limit, windows ≤ limit · M09 exhaustion non-decreasing within a half (only the declared HT recovery decreases it) · M10 positions in [0,1] · M11 card logic (second yellow ⇒ red; counts consistent) · M12 sequencing rules (03 §4) · M13 every event validates (Pydantic + JSON Schema) · M14 summary stats recomputable from events · M15 ratings in [3,10] · M16 `log_digest` matches · M17 nothing after `fulltime` except summary · M18 probabilities/xG in range · M19 abandonment rule consistent.
World (`verify_world`): W01 FK integrity · W02 squad rules (22–28 senior, ≥ 2 GK, formation coverage) · W03 `balance == opening + Σ ledger` per club · W04 closed-system identity with declared external accounts · W05 cached standings == recomputed · W06 `points = 3W + D`, Σgoals for = Σgoals against · W07 a player belongs to one squad · W08 contracts consistent with squad entries · W09 CA ≤ PA · W10 attribute/unit ranges · W11 unavailable players never in lineups · W12 valid schedule · W13 tick idempotence · W14 world hash determinism · W15 mood caps · W16 transfer leg symmetry · W17 date monotonic · W18 player stats = Σ match summaries.

`uv run verify --db league.sqlite` runs the whole catalogue on a live DB (also used by the health check).
