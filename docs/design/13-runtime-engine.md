# 13 — Runtime Engine (the thing that actually runs the channel)

Status: **PROPOSED (revision 4).** You're right: the product is not a command you run and read; it is a **service that starts, keeps running, and keeps producing the broadcast** — simulating ahead, advancing the world, replaying matches at broadcast pace, and feeding whatever sits downstream (commentary, voice, renderer, a stream encoder) for as long as it is left on. The CLIs from the original brief stay, but only as **thin developer/operator tools over the same library code** (`sim`, `seed`, `league`, `balance`, `verify`, `health`…). The primary executable is **`uv run engine`**.

## 1. What the engine does

```
                       ┌─────────────────────────── footystreams.runtime ───────────────────────────┐
                       │                                                                           │
  Clock ───────────────▶  Supervisor (tasks, restart/backoff, shutdown, single-instance lock)        │
 (system|scaled|virtual)│     │                                                                      │
                       │     ├─ WorldDriver ── daily tick pipeline (league layer, 07 §2) ──▶ DB      │
                       │     │       advances in-world days as the schedule requires                 │
                       │     ├─ SimulationBuffer ── process pool: simulate → verify → persist ──▶ DB │
                       │     │       keeps ≥ N matches `broadcast_ready` ahead of airtime            │
                       │     ├─ BroadcastScheduler ── programme: pre-match, match, HT, post, filler  │
                       │     ├─ MatchPlayer ── paced replay of stored, verified logs ──▶ EventBus    │
                       │     └─ HealthReporter ── heartbeat file, metrics, structured logs           │
                       │                                                                           │
                       │  EventBus ──▶ Sinks: NdjsonStdout · File · InMemory · (future) WebSocket,  │
                       │               Narrator pipeline, Renderer feed, Stream encoder             │
                       └────────────────────────────────────────────────────────────────────────────┘
```

- **Runs forever**: the loop is "while not stopping: ensure buffer → advance world → play what is scheduled". There is no "end"; seasons roll over (07 §7) and the next season's schedule is generated automatically. `--max-seasons N` / `--until-date D` exist for finite runs and tests.
- **Nothing is simulated on the live path.** The `SimulationBuffer` works ahead (default ≥ 1 matchday, ≥ 2 around weekends). The `MatchPlayer` only *replays verified logs* (10 §7).
- **Crash-only design:** the process can be killed at any instant (power loss, OOM, deploy). On restart it reloads the DB, finds its **playback cursor** (`engine_state: current_programme_id, match_id, last_emitted_seq`), and resumes mid-match without duplicates (sinks receive idempotent `(match_id, seq)` ids and a `resume` marker). Graceful `SIGINT/SIGTERM` finishes the current atomic write, persists the cursor, exits 0.
- **Single instance:** a lock file/DB advisory lock prevents two engines on one DB.
- **No web server in this task.** The engine publishes through the `EventSink` Protocol. Built-in sinks: NDJSON to stdout (pipe it anywhere), NDJSON file rotation, in-memory (tests). A WebSocket/HTTP sink is a ~100-line future adapter, not an architectural change.

## 2. Components and responsibilities (each one job)

| Component | Responsibility | Depends on (abstractions only) |
|-----------|----------------|---------------------------------|
| `Clock` (Protocol) | `now()`, `sleep_until(t)`; implementations `SystemClock`, `ScaledClock(speed)`, `VirtualClock` (tests/instant mode) | — |
| `EngineConfig` | frozen, validated settings: `db_path`, `pace` (`realtime \| scaled:N \| instant`), `buffer_depth_matchdays`, `sinks`, `time_scale` (in-world ↔ channel time), `safe_mode`, `max_seasons`, … | — |
| `Supervisor` | starts/monitors async tasks, restart with exponential backoff + circuit breaker, propagates shutdown, enforces the single-instance lock | `Clock` |
| `WorldDriver` | applies the daily tick pipeline up to the date the schedule requires; between matchdays advances days at the configured `time_scale` | league ports, `Clock` |
| `SimulationBuffer` | picks upcoming fixtures by kickoff order, runs `build_match_setup → simulate → verify_match → persist` in a process pool, sets `broadcast_ready` or quarantines + fallback (10 §7) | league, `verify`, persistence ports |
| `BroadcastScheduler` | maps the world's fixtures to a **programme** of timed blocks (`pre_match`, `match`, `half_time`, `post_match`, `matchday_magazine`, `filler`), choosing filler when the buffer or schedule has gaps | `Clock`, league read ports |
| `MatchPlayer` | replays a stored log at the programme's pace: waits until `start + event.clock.t / speed`, emits to `EventBus`, supports pause/resume/seek-to-cursor; replays are exactly the stored events (no randomness) | `Clock`, `EventBus`, match repository |
| `EventBus` | fan-out to sinks with **bounded queues per sink**; slow sinks never block the player: critical sinks (e.g. archive) apply backpressure to the *producer side only within a bounded window*, non-critical ones drop-oldest and log | `EventSink`s |
| `HealthReporter` | heartbeat file (`health.json`: last tick, buffer depth, quarantined count, current programme, lag), metrics counters, structured logs; read by `uv run health` and any external supervisor | `Clock` |

All are small classes with constructor-injected dependencies, wired in a single composition root (`runtime/main.py`). `runtime/` is the **only** package allowed to use the wall clock, `asyncio`, signals and the file system for locks — the sim, league and domain stay pure/deterministic (architecture test).

## 3. Broadcast programme and timing

`BroadcastScheduler` produces `ProgrammeBlock{id, kind, starts_at, duration, subject_ref}` from the world calendar:

- A **matchday** is a window of N in-world kickoff slots mapped to channel times (`time_scale`, default "1 in-world week ≈ 1 real day" — configurable); matches are **sequential on the one channel** (the 4 simultaneous kickoffs of a real matchday become back-to-back blocks, with the other results delivered as "meanwhile" updates later).
- Between matches: `half_time`, `post_match`, `matchday_magazine` (standings, results, transfer news from the `WorldEvent` feed) — these are **segment events** (`SegmentStarted/SegmentEnded{kind, subject, duration, facts}`) the future commentary/studio layers will fill; today they carry structured facts and a deterministic placeholder duration.
- Gaps (nothing scheduled, buffer starved) are filled by `filler` blocks (replays of archived matches/highlights selected by `significance`) so the stream never goes silent.
- Everything the engine emits is a **`BroadcastEvent`** = `MatchEvent | SegmentEvent | WorldNotice | EngineMarker (resume, restart)`; exported to `schemas/broadcast.schema.json` like the other contracts.

## 4. Pacing modes

| Mode | Behaviour | Used for |
|------|-----------|----------|
| `realtime` | `event.clock.t` seconds of match = seconds on the wall clock (a 90-minute match ≈ 97 minutes with stoppages); in-world days between matches advance at `time_scale` | Production |
| `scaled:N` | N× faster | Rehearsals, previews |
| `instant` | No waiting (VirtualClock jumps); runs a whole season in seconds | Soak tests, CI, dev (`uv run league` is `engine --pace instant --max-seasons 1` plus a standings printout) |

## 5. Failure handling

| Failure | Behaviour | Test |
|---------|-----------|------|
| Buffer starvation (sim slower than playback) | Scheduler inserts filler, SimulationBuffer raises priority; health shows `buffer_low`; never stalls the stream | virtual-clock test with an artificially slow sim |
| Match fails verification | Quarantine → fallback profile retry → filler + result-only fallback (10 §7) | fault-injection e2e |
| Sink raises/disconnects/slow | Isolated by bounded queue + timeout; others unaffected; reconnect with backoff; events not lost for the archive sink | rehearsal e2e (E5) |
| Task crash | Supervisor restarts it with backoff; repeated failure opens a circuit breaker → safe mode + health `degraded` | chaos test |
| Process killed | Restart resumes at cursor; no duplicate ledger entries/events; final state equals an uninterrupted run | E6 crash recovery |
| DB locked/slow/disk full | Retry with backoff for transient; degrade to read-only playback when writes fail repeatedly; loud health state | chaos test |
| Clock jump (NTP, sleep/wake) | Playback is anchored to a monotonic clock and re-syncs; no event bursts (bounded catch-up) | clock-skew test using VirtualClock |

## 6. Developer/operator CLIs (thin; same library code)

| Command | Purpose | Notes |
|---------|---------|-------|
| `uv run engine` | **Run the channel** (forever). `--db`, `--pace`, `--sink ndjson:stdout`, `--max-seasons`, `--safe-mode` | primary executable |
| `uv run sim --home KES --away HAR --seed 7` | One-off match with readable play-by-play | dev/QA, per the original brief |
| `uv run league --seed 1` | Play a season now and print standings | = engine in `instant` mode, one season |
| `uv run seed --seed N` | Regenerate the world | |
| `uv run verify --db …`, `uv run health --db …` | Operator checks | exit non-zero on problems |
| `uv run export-schemas`, `uv run balance …`, `uv run changelog …`, `uv run check …` | Tooling | |

## 7. Milestone and tests (see 06 M12)

Delivered in **M12**: runtime package, virtual-clock engine tests (season in seconds), crash/restart, single-instance, shutdown signals, starvation, sink isolation, pacing accuracy (±50 ms over a match on the virtual clock; ±250 ms drift per hour on a real-clock smoke test), `engine` end-to-end (E12: start the real process, consume NDJSON from stdout for one accelerated matchday, SIGTERM, restart, verify continuity), plus the Dockerfile/compose and restart policy in M14.
