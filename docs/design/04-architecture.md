# 04 — Architecture

Status: **PROPOSED (Phase 1).**

## 1. Layers and the dependency rule

```
                      ┌────────────────────────────────────────────────┐
                      │ runtime  (the long-running ENGINE: `uv run engine`, see 13)
                      │ cli      (thin dev/ops tools: sim · league · seed · verify · health · balance …)
                      └───────────────┬────────────────────────────────┘
                                      │
   ┌───────────────┐   ┌──────────────▼───────────┐   ┌─────────────────────────┐
   │ extensions    │   │ league                    │   │ persistence             │
   │ Protocols +   │   │ schedule, standings,      │   │ ports (Protocols),      │
   │ stub types    │   │ attendance, weather gen,  │   │ SQLAlchemy repos,       │
   │ (Narrator,    │   │ build_match_setup,        │   │ in-memory repos, UoW,   │
   │ MemoryUpdater,│   │ post_match (pure deltas), │   │ Alembic                 │
   │ Voice…)       │   │ finance                   │   └───────────┬─────────────┘
   └───────┬───────┘   └──────────────┬────────────┘               │
           │                          │                            │
           │              ┌───────────▼────────────┐               │
           │              │ sim  (PURE)             │               │
           │              │ simulate_match(...)     │               │
           │              └───────────┬─────────────┘               │
           │                          │                             │
        ┌──▼──────────────────────────▼─────────────────────────────▼──┐
        │ events   (Pydantic discriminated union, summary, context)    │
        └──────────────────────────┬────────────────────────────────────┘
                                   │
        ┌──────────────────────────▼────────────────────────────────────┐
        │ domain   (Pydantic models, ids, enums, ratings/valuation pure fns) │
        └────────────────────────────────────────────────────────────────┘
```

**Rule:** imports point *down*. `domain` imports nothing from the project. `events` → `domain`. `sim` → `events`, `domain` (and static tables passed in). `league` → `sim`, `events`, `domain`, and the persistence **ports** (not implementations). `persistence` → `domain`, `events`. `extensions` → `domain`, `events` only (never `sim`/`persistence`). **`runtime`** (the engine, 13) → `league`, `sim` (via a process pool), `verify`, persistence ports, `extensions`; it is the **only** package allowed to use the wall clock, `asyncio`, signals and lock files. `cli` is a composition root like `runtime/main.py`: it wires the same library code into one-shot commands. `seed` generation → `domain` (+ static data). An AST-based architecture test enforces the matrix and also bans `sqlalchemy`, `sqlite3`, `os`, `pathlib`, `open`, `random`, `time`, `datetime.now`, `numpy` inside `footystreams/sim`.

## 2. Package layout

```
FootyStreams/
├─ pyproject.toml            # uv, ruff, mypy(strict + pydantic plugin), pytest, scripts
├─ uv.lock
├─ alembic.ini
├─ README.md
├─ docs/design/              # this document set
├─ data/
│  ├─ static/                # hand-authored YAML: formations, roles, traits, injuries, cultures, archetypes, climate, sim_config.default.yaml
│  └─ worlds/default/        # committed generated world (seed 1): JSON files + manifest.json
├─ schemas/                  # exported JSON Schema (committed; drift-tested)
├─ alembic/versions/
├─ src/footystreams/
│  ├─ domain/
│  │  ├─ types.py            # Id NewTypes, Attribute/Competence/Reputation/Disposition/Level/AbilityScore, Unit, Signed, Money, Pos, EntityRef, enums
│  │  ├─ person.py  player.py  manager.py  staff.py  referee.py  media.py
│  │  ├─ club.py  stadium.py  finance.py  tactics.py
│  │  ├─ competition.py  fixture.py  standings.py
│  │  ├─ match.py            # Match, TeamSheet, PlayerSnapshot, Weather
│  │  ├─ memory.py  relationship.py  proposals.py
│  │  ├─ ratings.py          # compute_current_ability, role ratings, team_rating (pure)
│  │  ├─ valuation.py        # market_value (pure)
│  │  └─ usage.py            # S/L/R field registry + check helpers
│  ├─ events/
│  │  ├─ base.py  context.py  types.py (union)  summary.py  ratings.py  annotate.py
│  ├─ sim/
│  │  ├─ api.py              # simulate_match, run_match
│  │  ├─ config.py           # SimConfig (frozen Pydantic) + load/hash
│  │  ├─ rng.py              # SimRng, fork
│  │  ├─ mathx.py            # squash, gauss, interp — IEEE-exact only
│  │  ├─ tables.py           # loaded static tables container
│  │  ├─ state.py            # mutable internal state (dataclasses/slots)
│  │  ├─ geometry.py  positioning.py  pressure.py
│  │  ├─ decision.py  actions/ (pass_, dribble, tackle, shot, keeper, clearance)
│  │  ├─ setpieces.py  discipline.py  referee.py  injuries.py  fatigue.py
│  │  ├─ weather.py  homeadv.py  momentum.py  clock.py
│  │  ├─ manager_ai.py       # checkpoints, substitution & tactics policy
│  │  ├─ review.py           # video review (M10)
│  │  └─ emit.py             # builds validated events + ctx tags
│  ├─ league/
│  │  ├─ schedule.py  standings.py  calendar.py  attendance.py  weather_gen.py
│  │  ├─ setup.py            # build_match_setup(reader, fixture) -> MatchSetup
│  │  ├─ lineup_ai.py        # pick XI/bench/roles/set-piece takers for a club
│  │  ├─ post_match.py       # (MatchResult, WorldReader) -> WorldDelta  (pure)
│  │  ├─ finance.py          # matchday revenue, wage accrual, ledger entries
│  │  ├─ clock.py            # WorldClock, daily tick pipeline (07 §2)
│  │  ├─ mood.py             # resolve_mood, rule-based modifiers, WorldEventGenerator
│  │  ├─ development.py      # training micro-steps, season progression, retirement, youth intake
│  │  ├─ contracts.py        # renewals, expiry
│  │  ├─ transfer_ai.py      # needs, shortlists, bids, negotiation, OUTSIDE_WORLD market
│  │  ├─ rollover.py         # off-season block (07 §7)
│  │  └─ season.py           # SeasonRunner (orchestrates; uses ports)
│  ├─ persistence/
│  │  ├─ ports.py            # repository Protocols, UnitOfWork, WorldReader
│  │  ├─ memory_impl.py      # in-memory repos (tests, CLI --no-db)
│  │  └─ sql/
│  │     ├─ tables.py        # SQLAlchemy 2.x declarative (typed Mapped[...])
│  │     ├─ repos.py  uow.py  codec.py (Pydantic↔row)  engine.py
│  ├─ seed/
│  │  ├─ names.py  generators/ (players, managers, clubs, media, referees, relationships)
│  │  ├─ coherence.py        # validation of the generated world
│  │  └─ world_io.py         # canonical JSON writer/reader, manifest, hashing
│  ├─ extensions/
│  │  ├─ protocols.py        # Narrator, MemoryUpdater, VoiceSynthesizer, EventSink
│  │  ├─ types.py            # CommentaryLine, MemoryProposal union, AudioClip, BroadcastContext
│  │  └─ stubs.py            # NullNarrator, NullMemoryUpdater, NullVoice (+ test echo narrator)
│  ├─ runtime/               # THE ENGINE (13): main.py (composition root), config.py, clock.py, supervisor.py, world_driver.py, sim_buffer.py, scheduler.py, match_player.py, bus.py + sinks/, health.py, lock.py
│  ├─ verify/                # THE invariant catalogue (10 §9): verify_match, verify_world, verify_season → list[Violation]; used by tests, --strict, soak, production pre-air gate
│  ├─ analytics/             # read-only pass maps / xT / pressing metrics from events (M7+)
│  ├─ tools/                 # export_schemas.py, balance.py (numpy), changelog.py, golden.py, profile.py, digest.py
│  └─ cli/                   # sim.py, league.py, seed.py, export_schemas.py, balance.py, render.py (text play-by-play)
└─ tests/
   ├─ unit/  property/  invariants/  golden/  statistical/ (marker: slow)  persistence/  architecture/  cli/
```

`render.py` (text play-by-play) is a **plain deterministic formatter** (`"61' GOAL! Brae (HAR) …"`) used by the CLI; it is not commentary and has no LLM.

**Why there is still a CLI:** the product is the **engine** — a process that starts and keeps running (13). The commands from the original brief are kept as thin developer/operator tools over the *same* library functions (no duplicated logic): they are how we inspect one match, regenerate a world, run a season quickly, and operate the system.

Entry points in `pyproject.toml`:

```toml
[project.scripts]
engine = "footystreams.runtime.main:app"        # run the channel (forever)
sim = "footystreams.cli.sim:app"                # one match, readable play-by-play (dev/QA)
league = "footystreams.cli.league:app"          # = engine --pace instant --max-seasons 1 + standings
seed = "footystreams.cli.seed:app"
verify = "footystreams.cli.verify:app"
health = "footystreams.cli.health:app"
export-schemas = "footystreams.cli.export_schemas:main"  # argparse; Typer deferred
balance = "footystreams.cli.balance:app"
changelog = "footystreams.tools.changelog:app"
check = "footystreams.tools.check:app"
```

so `uv run sim --home KES --away HAR --seed 7` works exactly as requested (`--home` takes a club id **or** its 3-letter code) and `uv run engine` runs the league continuously.

Dependencies: runtime `pydantic>=2.7`, `sqlalchemy>=2.0`, `alembic`, `pyyaml`, `typer`; dev `pytest`, `pytest-xdist`, `hypothesis`, `ruff`, `mypy`, `types-PyYAML`; group `tools`: `numpy` (balance tooling only; not imported from `sim`). `rich` is optional for table output in the CLI.

## 3. Key function signatures

```python
# sim/api.py — the pure core
def simulate_match(setup: MatchSetup, seed: int, config: SimConfig, tables: StaticTables) -> Iterator[MatchEvent]: ...
def run_match(setup: MatchSetup, seed: int, config: SimConfig, tables: StaticTables) -> MatchResult: ...

# league/setup.py
def build_match_setup(reader: WorldReader, fixture: Fixture, *, rng: SimRng) -> MatchSetup: ...   # may use rng for weather/attendance noise; separate stream from sim

# league/post_match.py (pure)
def derive_world_delta(result: MatchResult, reader: WorldReader, rules: LeagueRules) -> WorldDelta: ...
class WorldDelta(BaseModel):
    player_state: list[PlayerStateUpdate]      # form, morale, fatigue, sharpness, fitness, injuries, suspensions
    stats: list[PlayerStatsIncrement]
    ledger: list[LedgerEntry]                   # matchday income, per-match wage accrual, bonuses
    standings_update: StandingsUpdate
    fixture_update: FixtureUpdate               # status, match_id, score
    manager_updates, board_updates, fanbase_updates ...
```

`MatchResult{events, summary, setup_ref, seed, config_hash, log_digest}`.

## 4. Persistence design

### 4.1 Storage shape: relational keys + validated JSON documents

Each aggregate has a table with (a) real columns for **identity, foreign keys, and everything you query/filter/sort/aggregate on**, and (b) a `data` JSON column holding the full Pydantic model (validated on read and write by `codec.py`). Reasons: the models are deep (≈ 120 fields on a player); a fully normalised mapping would be hundreds of columns and join tables whose only consumer is Pydantic; schema evolution of rich nested models is far easier with a `schema_version` per row plus Pydantic migration functions than with Alembic migrations for every field. Alembic still owns everything *relational*. Domain code never sees ORM objects — repositories take and return Pydantic models.

| Table | Columns (besides `data JSON`, `schema_version`, `rev`) |
|-------|--------------------------------------------------------|
| `world_meta` | `key`, `value` — seed, generator version, current in-world date, sim_version, config_hash |
| `nations`, `cities` | id, name, … (small reference tables) |
| `clubs` | id, short_code (unique), name, reputation, balance, city_id |
| `players` | id, club_id (null=free agent), primary_position, ability_current, age_dob, squad_status, injured (bool), suspended (bool), market_value |
| `contracts` | id, player_id, club_id, wage_weekly, start, end |
| `squad_entries` | club_id, player_id, squad_number, status (unique club+number) |
| `managers`, `staff`, `referees`, `media_personalities` | id, club_id/role, reputation, … |
| `competitions`, `seasons`, `matchdays`, `fixtures` | ids, season, matchday, home, away, kickoff, status, match_id |
| `matches` | id, fixture_id, home/away club, date, seed, config_hash, sim_version, home_goals, away_goals, log_digest, `data` (Match incl. sheets) |
| `match_events` | `(match_id, seq)` PK, `type`, `t`, `significance`, `data` (the event JSON); composite index `(match_id, type)`; **append-only, ground truth** |
| `match_summaries` | match_id PK, `data` |
| `event_annotations` | event_id, `data` (non-causal, §03-6) |
| `standings_snapshots` | season_id, after_matchday, `data` |
| `player_season_stats` | `(player_id, season_id, competition_id, club_id)` PK, numeric columns |
| `ledger_entries` | id, club_id, date, category, amount, ref_type, ref_id — append-only |
| `injury_records` | id, player_id, type, started_on, expected_return_on, recovered_on |
| `relationships` | id, a_kind,a_id,b_kind,b_id, kind, strength |
| `memories` | id, owner_kind, owner_id, kind, status, importance, valence, created_on, last_recalled_on, visibility_scope, `data` (indexed on owner/status/created) |
| `proposals` | id, kind, status, proposed_by, created_on, applied_on, rejection_reason, `data` |

`rev` (integer) is incremented on every update and checked on write (optimistic concurrency) so a future asynchronous LLM applier cannot clobber a league update.

**This is still a relational SQL database, not NoSQL.** Sorting, filtering and aggregating by match, matchday, date, club, score, event type, time or significance all hit real indexed columns (`matches(season_id, matchday, date, home_club_id, away_club_id, home_goals, away_goals)`, `match_events(match_id, seq, type, t, significance)`, `player_season_stats` numeric columns, `ledger_entries(club_id, date, category, amount)`). Only deeply nested, rarely-sorted structure (attribute blocks, tactics, personality, kit specs) sits in the JSON blob. Two escape hatches if you later need to query inside a blob: (a) promote the field to a real column in an Alembic migration, or (b) add an SQLite **generated column** over `json_extract(data, '$.path')` with an index — no data rewrite. If a query pattern turns out to dominate, we promote; the repository interface does not change.

**New tables (revision 2):** `state_modifiers(id, owner_kind, owner_id, kind, start_on, expires_on, visibility, origin, data)`, `world_events(id, date, kind, visibility, origin, data)`, `world_log(date, stage, delta_hash)`, `transfer_windows`, `transfer_listings(player_id, club_id, status, asking_price)`, `transfer_bids(id, window_id, player_id, from_club_id, to_club_id, fee, status, round)`, `contract_offers`, `transfers(id, player_id, from, to, fee, completed_on)`, `scout_reports`, `development_entries(player_id, date, attr, delta, cause)`, `manager_knowledge` (reserved). `OUTSIDE_WORLD` is a reserved club row (`clb_outside`) so foreign-market legs keep foreign-key integrity.

### 4.2 Repository layer (swap-ready)

`persistence/ports.py` defines Protocols — e.g. `PlayerRepository.get(id)`, `list_by_club(club_id)`, `save(player)`, `save_many`, `ClubRepository`, `FixtureRepository`, `MatchRepository.append_events(match_id, events)`, `LedgerRepository.append(entries)`, `MemoryRepository.add/search(owner, status)/update`, `ProposalRepository`, … plus read-only `WorldReader` (what `build_match_setup` and `post_match` see) and `UnitOfWork` (`with uow: …; uow.commit()`; one transaction per match: events + summary + world delta). Implementations: `persistence/sql/*` (SQLAlchemy 2.x, SQLite with WAL, `PRAGMA foreign_keys=ON`) and `persistence/memory_impl.py` (dict-backed; used by most tests and by `sim` when run directly from JSON). Swapping to Postgres later = new `sql/engine.py` config plus verifying JSON column types; no domain change.

### 4.3 Migrations
Alembic with `render_as_batch=True` (SQLite). `0001_initial` generated from the SQLAlchemy metadata and then reviewed by hand. Tests: `alembic upgrade head` on an empty DB, `alembic check` (model/metadata parity), and a downgrade/upgrade round trip.

### 4.4 Ground truth vs. what an LLM may touch

**Ground truth (deterministic code only; the LLM layer has no write path):** attributes and all player/manager/club state; contracts; finances and ledger; fixtures, results, standings, stats; **every match event, summary, digest**; injuries; suspensions; the calendar; the world seed.

**Narrative layer (may be *proposed* to, never written directly):**
- `memories` — facts (`origin=sim_fact|derived`) are written by deterministic code from results; `origin=proposed` entries (reflections, interactions, opinions) enter via proposals.
- `relationships` — bounded deltas (e.g. |Δstrength| ≤ 0.1 per match, ≤ 0.25 per week), new `friend/feud/running_joke` links.
- `media` persona drift: catchphrase usage counts, running jokes.
- **`StateModifier`s** ("a bad week"): the LLM may propose whitelisted kinds with magnitude ≤ 50% of the deterministic cap, ≤ 1 per entity per 7 days, each citing an existing `WorldEvent`/event/memory involving the owner; the **sum of all sources is hard-capped** by `MoodConfig` (07 §3). These *do* change match performance — through the frozen `PlayerSnapshot.mood`, never mid-match.
- `WorldEvent`s of origin `proposed` (stories, rumours) — cosmetic until a deterministic rule or an accepted modifier gives them effect.

**Proposal envelope** (`domain/proposals.py`, table `proposals`): `{id, kind, payload, proposed_by: {component, model_id, prompt_hash}, created_on, status: pending|accepted|rejected|applied, rejection_reason}`. A deterministic `ProposalApplier` (later) validates: payload schema, entity existence, referenced `event_ids` actually exist in `match_events` and involve the claimed entities, bounds and rate limits, visibility rules, and consistency with ground-truth facts. Only the applier writes. **The LLM can never alter a match in flight or a recorded result.**

## 5. Extension points (Protocols; defined in this task, implemented later)

```python
# extensions/protocols.py
class Narrator(Protocol):
    """Events -> commentary lines. Stateful per match; may call an LLM. Must be cheap to skip."""
    async def begin_match(self, ctx: BroadcastContext) -> None: ...
    async def on_event(self, event: MatchEvent) -> Sequence[CommentaryLine]: ...
    async def end_match(self, summary: MatchSummary) -> Sequence[CommentaryLine]: ...

class MemoryUpdater(Protocol):
    """Match results -> *proposed* memory/relationship changes. Never writes to the DB."""
    async def propose(self, result: MatchResult, delta: WorldDelta, world: WorldReader,
                      memories: MemoryReader) -> Sequence[MemoryProposal]: ...

class VoiceSynthesizer(Protocol):
    """Speech request (text + emotion + voice profile) -> audio. Provider-agnostic; see 12-voice-and-tts.md."""
    capabilities: SynthCapabilities
    async def synthesize(self, request: SpeechRequest) -> AudioClip: ...

class EventSink(Protocol):          # future broadcast pacer / websocket / renderer feed
    async def publish(self, event: MatchEvent) -> None: ...

# sim/manager_ai.py — re-exported in extensions/; the learning-manager seam (08 §2)
class ManagerPolicy(Protocol):
    policy_id: str
    policy_version: str
    def decide(self, obs: ManagerObservation, rng: SimRng) -> Sequence[ManagerAction]: ...
```
The v1 rule-based/softmax manager is `RulesPolicyV1`. `ManagerObservation`/`ManagerAction` are typed Pydantic models, so learned policies (offline-trained, content-addressed, recorded on the `TeamSheet`) need no sim changes. Likewise the sim's internals are composed of Protocol-typed components (`PositioningModel`, `DecisionModel`, `ResolutionModel`, `PressModel`, `SetPieceModel`, `ShotQualityModel`, …) chosen by `SimConfig.model_profile` — see 08-roadmap.

```python
# extensions/types.py
class BroadcastContext(BaseModel):   # read-only snapshot given to the narrator
    match_id; preamble: MatchPreamble; crew: BroadcastCrew; personalities: dict[MediaId, MediaPersonality]
    memories: MemoryDigestView | None        # populated by future retriever
class CommentaryLine(BaseModel):
    id, match_id, speaker_id: MediaId, text: str, event_ids: list[str], emotion: Literal[...],
    energy: Unit, priority: Unit, est_duration_ms: int | None, interrupts: bool
class MemoryProposal = Annotated[Union[CreateMemory, ReinforceMemory, AdjustRelationship, ConsolidateMemories, ArchiveMemory], Field(discriminator="op")]
class SpeechRequest(BaseModel):  line_id, text, voice: VoiceProfile, emotion, energy: Unit, prosody_hints, overlaps_with, interjection   # 12 §2
class AudioClip(BaseModel):  uri: str, format: Literal["wav","mp3","ogg"], sample_rate: int, duration_ms: int, word_timings: list[WordTiming] | None, line_id: str
```

`extensions/stubs.py` ships `NullNarrator`, `NullMemoryUpdater`, `NullVoice` and a test-only `EchoNarrator` (formats `ctx.headline`) so the plumbing (event → narrator → line → voice) has a runnable, tested seam without any model call. Async Protocols because every real implementation is I/O-bound; the pure/sync sim feeds them through a thin adapter later. Because `Pos`, `ctx.significance`, `clock.t` and `chain_id` are on every event, a pacer can replay the log at 1× real time (a 90-minute match = ~97 real minutes with stoppages) or time-compressed for highlight reels.

## 6. Configuration, versioning and reproducibility

- `SimConfig` (frozen Pydantic, ≈ 80 fields grouped: `pass`, `shot`, `tempo`, `home_adv`, `fatigue`, `injury`, `discipline`, `referee`, `manager_ai`, `weather`, `stoppage`, `review`), loaded from `data/static/sim_config.default.yaml`, overridable by `--config`. `config_hash = sha256(canonical json)`.
- `SIM_VERSION` (semver string in code) bumps when sim logic changes in a way that alters output. Every match record stores `(sim_version, config_hash, seed)`; replay with a different `sim_version` raises unless forced.
- `SCHEMA_VERSION` for events/models, see 03 §8.
- World reproducibility: `seed` command writes `manifest.json` with generator version + content hash.
- The league run uses a **separate** stream hierarchy from the match sim: `season_rng = SimRng(world_seed).fork("season:<id>")`; each match seed = `derive(season_rng, fixture_id)`, so replaying fixture N in isolation is possible.

## 7. Errors, logging, observability

Domain validation errors surface as Pydantic `ValidationError`; the CLI converts to exit code 2 with a readable message. `sim` has no logging; `league`/`persistence`/`cli` use stdlib `logging` (structured `key=value`), default WARNING. A `--strict` flag re-validates every event and checks invariants live (used by tests and nightly).

## 8. Operational safety for a 24/7 channel (summary; requirements in 10 §7, engine design in 13)

- **The engine is crash-only and supervised:** playback cursor persisted; restart resumes mid-match; single-instance lock; graceful shutdown; health heartbeat file.
- **Pre-simulation buffer:** matches are simulated and persisted ahead of airtime; the live path only replays stored, verified logs.
- **Pre-air gate:** `verify.verify_match()` (same code as the tests) runs in production; `Fixture.status` gains `broadcast_ready` and `quarantined`. Quarantine ⇒ retry on the fallback `model_profile` with the same seed ⇒ else filler content + a deterministic result-only fallback so the league continues.
- **Matchday parallelism:** the 4 matches of a matchday are independent pure computations → `ProcessPoolExecutor`, results merged in fixture order (deterministic); persistence happens in the parent in one transaction per match.
- **Idempotent stages** with `world_log` digests; backup-before-migrate; `uv run health` and `uv run verify` commands; `--safe-mode`.

## 9. Quality tooling

- **ruff:** `select = ["E","F","I","B","UP","SIM","RUF","PL","C4","C90","PT","S","D","N","FBT","BLE","TRY","PERF","ARG","ERA"]` with `max-complexity = 8`, `max-args = 5`, `max-statements = 30`, Google-style docstrings, line length 100, format via `ruff format`; documented per-file ignores for tests only.
- **mypy:** `strict = true`, `plugins = ["pydantic.mypy"]`, `disallow_any_explicit` on `sim/` and `domain/`.
- **pytest:** plugins `pytest-xdist`, `pytest-randomly`, `pytest-timeout`, `pytest-socket`, `pytest-cov`, `pytest-benchmark`, `hypothesis`; markers `statistical`, `soak`, `chaos`, `golden`, `perf`, `slow`; tiers T0–T3 (10 §2).
- **Other gates:** `vulture` (dead code), `pylint` duplicate-code only, `pip-audit`, `mutmut` (Linux, nightly), `changelog check`.
- Single entry point: `uv run check [--tier fast|pr|nightly|release]` runs the right set; pre-commit runs T0.
- Windows + Linux (+ Python 3.12/3.13) in CI; determinism across platforms is a stated requirement.
- Details of standards and budgets: 11-engineering-standards.md; test strategy: 10-testing-strategy.md.
