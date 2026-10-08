# 08 — Roadmap and Forward Compatibility

Status: **PROPOSED (revision 2).** This file records *future scope* the user has asked us to design for, and the specific hooks Phase 1/2 build now so these additions are extensions, not rewrites. None of the "later" items is implemented in this task.

## 1. Simulation depth roadmap

The v1 sim (02) already contains a positional layer, pressure model, action-chain decisions, xG and xT surfaces. The goal is to grow it toward Football-Manager-and-beyond tactical richness: **gegenpressing, passing triangles, pass maps, xG/xA/xT/PSxG, pressing traps, build-up structures, defensive blocks, set-piece routines.**

| Capability | v1 (this task) | Later (v2/v3) | Hook that exists now |
|-----------|----------------|---------------|----------------------|
| **Pass maps / networks** | Every pass event has `pos`, `end_pos`, `passer_id`, `receiver_id`, `kind`, `outcome`, `progressive`, `xt_gain`, `under_pressure` → pass maps and passing networks are computable from the log | Zone-to-zone flow matrices, third-man passes, line-breaking pass flags, pass value (xT) by player/zone | Event schema; `analytics/` package computing maps from events (read-only) |
| **xG / xA / xT / PSxG** | `xg` on shots, `psxg` on saves, `xt_gain` on passes, `xg` on goals; match `xg_timeline`; per-player xG/xA in `PlayerMatchStats` | Better models (shot-freeze-frame defenders, GK position, assist type), calibrated to *this* league's outcomes | `ShotQualityModel` Protocol in sim; model id recorded in `config_hash` |
| **Gegenpressing / counter-press** | `transitions.on_loss = counter_press` raises press intensity for ~5 s; costs energy | Explicit *press-trigger* zones, 5-second regain probability from local density, press traps (force play to a side then jump), PPDA, pressing resistance (receiver `first_touch`/`composure`), cover shadows | `PressModel` Protocol; `press_trigger`, `compactness`, `press_role` already in tactics and roles |
| **Triangles / support geometry** | Receiver options scored by openness/lane; roles offset positions | Role-defined **support offsets** that form triangles and diamonds around the carrier, rotations (fullback inverts, 8 drifts wide), third-man runs; "number of passing options within a triangle" as a first-class feature in the decision model | `PositioningModel` + `DecisionModel` Protocols; role table is data-driven (`offset_in/out[phase]`) so new behaviours are YAML additions first |
| **Defensive blocks** | Line height, compactness, offside trap | Block height transitions, man-oriented vs. zonal behaviour, pressing lines by phase | `out_of_possession` tactics block; `PositioningModel` |
| **Set-piece routines** | Corner/FK routines enumerated, resolved as aerial duels + shot | Named routines (blocker screens, near-post flick-ons), player-specific assignments | `set_pieces` tactics block; `SetPieceModel` Protocol |
| **Tracking data / renderer** | Positional layer exists internally | **`frame` events**: 22 player + ball positions at a fixed cadence (default every 1 s of match time) emitted as an opt-in event type (`SimConfig.emit_frames`, off by default; on for the renderer). Heatmaps, shape analysis, off-ball movement visualisation | `frame` is a reserved type in the union from v1.0 (03 §3); positions already computed |
| **Player-specific behaviour** | Traits and roles bias utilities | Trait/role learning; individual tendencies from stats (heat maps become *inputs*) | `traits.yaml` data-driven |

**How v2 is added without breaking v1:** the sim is a composition of small Protocol-typed components (`PositioningModel`, `DecisionModel`, `ResolutionModel`, `PressModel`, `SetPieceModel`, `ShotQualityModel`, `RefereeModel`, `InjuryModel`, `FatigueModel`), selected by `SimConfig.model_profile` (`"v1"`, later `"v2"`). Each profile has its own golden digests and `SIM_VERSION`. Events only gain *optional additive fields* (minor schema version), never change meaning. The balance harness runs per profile and its targets are profile-scoped. The event log and `analytics/` stay the single interface to everything downstream.

**Tactics growth path.** `TeamTactics` is already a versioned module registry (01 §3.8). Each row above that needs new tactical vocabulary becomes a **new module** (`gegenpress`, `support_geometry`, `overloads`, `rest_defence`, `positional_zones`, `set_piece_routines`, `individual_tendencies` are stubbed as reserved) plus the matching sim component; stored tactics keep working across sim versions via the `TacticsView` defaults.

**Voice/TTS** is a leaf layer behind `VoiceSynthesizer v2` (12): provider choice deferred to a bake-off; the engine (13) already provides the slots (segments, `EventSink`s) it will use.

## 2. Learning and adaptive managers (future)

Planned: AI managers that **learn as they go** — tactics that work against particular opponents or in particular game states are used more; substitution timing improves; formation choices adapt to the squad and league. Because the sim is pure, deterministic and fast (≈ 100 ms/match), it doubles as a training environment.

Hooks built now:

- **`ManagerPolicy` Protocol** (in `sim/manager_ai.py` and re-exported in `extensions/`): `decide(observation: ManagerObservation, rng) -> ManagerAction`. The v1 rule-based/softmax AI is just one implementation. `ManagerObservation` and `ManagerAction` are typed Pydantic models (the observable state in 02 §11; the action space: substitution, formation, mentality, instruction slider changes, role changes), so a learned policy plugs in with no sim change.
- **`policy_id` + `policy_version` are recorded on every `TeamSheet`/match record**, so a match with a learned policy is exactly replayable (policy snapshots are content-addressed and stored; stochasticity only via the manager RNG stream).
- **`ManagerKnowledge` (reserved table)**: per-manager, deterministic, numeric experience — e.g. opponent-specific tactic outcomes (win/xG-difference by `(opponent, formation, mentality)`), substitution outcome stats, a Bayesian/bandit state. Updated by a post-match updater from facts (like finances). *This is distinct from `MemoryRecord`*: knowledge drives decisions; memories drive narrative. An LLM may later *narrate* what a manager "learned" but cannot edit the numbers.
- **Training harness (later):** run many seeded matches/seasons with a policy vs. baseline using the `balance` infrastructure; promote a policy only if it improves points-per-game without breaking balance bands (guard against degenerate exploits, e.g. a policy that wins by exploiting a sim artefact — which is why balance bands are tested per policy).
- **Fairness/realism guard:** policy actions pass the same constraints as AI actions (window limits, cooldowns, `adaptability`, `formation_proficiency`), and learned behaviour is rate-limited by `tactical_knowledge` so a "dim" manager cannot suddenly play perfect football.

## 3. Other planned extensions (schemas/seams already reserved)

| Item | What is reserved now |
|------|----------------------|
| **Cup competitions** | `Competition.kind=cup`, `CupFormat`, `extra_time`/`shootout` in `MatchRules`, reserved event types (`shootout_kick`, `extra_time_start`), `clock.period` 3–4 |
| **Youth/reserve teams and leagues** | `squad_status` values, `YouthAcademy`, `Player.squad_status=youth`; a `Competition` with its own fixtures can host youth matches with the same sim |
| **Loans** | `Loan` table reserved; squad_status `loaned_out`; `TransferBid` has `kind` for loan later |
| **Promotion/relegation, more divisions** | `LeagueFormat.promotion_spots/relegation_spots`; `Competition.tier`; `Season` supports multiple competitions |
| **Manager sacking/appointment** | Board confidence, objectives; schema only for now (decision O1, 09) |
| **Women's league / mixed squads** | `gender` on `Person`; names generator parameter |
| **LLM commentary, TTS, renderer, server** | Protocols in 04 §5; `frame` events; `MediaPersonality`; `WorldEvent` feed; `StateModifier.public` storylines (wishlist and proposed order: section 3a) |
| **LLM-assisted world events and press** | `proposals`; `WorldEvent.origin=proposed`; mood bounds (07 §3.4) |
| **Memory logic** | Full schema, decay/retrieval design (01 §7), proposals applier |
| **Scouting game** | `ScoutReport`, noisy perceived ability already used internally by AI |
| **Injuries depth** | `injury_types.yaml` extensible; rehab/medical staff effects |
| **Analytics** | Read-only `analytics/` package over events (pass maps, xT, pressing metrics) — added as soon as the first v2 feature needs it |

## 3a. Wishlist: the studio, social and stream layer (after M13)

Status: **WISHLIST, not scheduled.** The owner wants the league to become a 24/7 pixel-art channel: a live broadcast with matches, studio shows, pundits, a ticker and replays, plus the media world around it. M12 (the engine) and M13 (the seams) are the foundation; everything below is built on them and needs its own design document ("14 - studio, social and stream") before any milestone is cut.

### The intended shape

A site around a live video stream in a styled "monitor" frame, with replays and a radio stream; the scenes are drawn in the browser in low-resolution pixel art scaled up without smoothing (a canvas, a cast of characters, a ticker, show timing). The pipeline is a browser scene, then a recording of it, then a stream encoder, then the host.

### Wishes

| Wish | What it is | Foundation that exists |
|------|-----------|------------------------|
| **Live match broadcast** | A pixel pitch drawn from `frame` events (22 players and the ball, 1 s apart, smoothed to about 30 fps), with goal, card and substitution overlays, a scoreboard, replays of goals | `frame` events (opt-in), M12 engine and sinks, player `appearance`, club `KitSpec` |
| **Studio shows** | Desk, anchors, lower thirds, ticker, speech bubbles; pre-match, half-time, post-match and matchday magazine segments | M12 programme blocks and segment events, `MediaPersonality`, `broadcast_traits` |
| **Pundit and news shows** | A panel of pundits and a news desk discussing the matchday, transfers, injuries and storylines | `WorldEvent` feed, `StateModifier.public` storylines, proposals (`origin=proposed`) |
| **Commentary and voices** | LLM-phrased lines from facts only, spoken by TTS voices with word timings for the bubbles | M13 narrator and voice seams, `EchoNarrator` and `NullVoice` fallbacks |
| **Social media** | Posts by players, reporters and fans on events (goal, red card, transfer): player voice from personality, fan tone from the fanbase's passion and toxicity; a feed page | Person traits, `Fanbase`, `WorldEvent` feed; posts stored with their source and never written back into the world without the proposals path |
| **Newspapers** | A daily edition from results, tables, transfers and match reports, rendered as a page or an image | Standings, match summaries, `WorldEvent` feed |
| **Streaming and site** | A recorder and encoder to the stream host; an own site with the live embed, replays, standings, the social feed and the papers | M12 health and heartbeat |

### Ground rules for all of it

- The simulation and the event log stay the single source of truth. Text, voice and pictures *phrase and show* facts; they never change them, and a failure or a slow layer is contained by timeouts, bounded queues and null fallbacks (design 10 section 7, E5).
- No art assets are needed to start: sprites are drawn in code from the seeded appearance and kit data.
- The renderer is TypeScript in the browser, in its own folder outside the Python package, with types generated from the broadcast JSON schema (the schema export M12 deferred to the next schema bump).
- A fictional league has no real-world headlines to credit; every news item comes from the world's own events.

### Proposed order (to confirm when the design is written)

1. The design document and its decisions (below).
2. A silent browser viewer fed by an engine sink: a live pixel match. A file-replay **prototype** of the picture (not this step) lives in `viewer/`: it reads a recorded `--frames` log through one `onEvent` function, so the live sink can replace the file reader.
3. Studio scenes with templated scripts (no LLM).
4. LLM commentary and TTS behind the M13 seams, with fallbacks.
5. Text products: social feed, newspapers, pundit shows.
6. Recording, encoding and the site.
7. **M14b**: soak, chaos, fault injection, shadow run, container and release notes across the whole chain, so they cover the renderer, encoder and narrator. The slices that harden what already exists (verify and health CLIs, the quarantine fallback profile, safe mode, the fuzz harness, the mutation job) may move earlier as **M14a**. Not yet agreed.

### Decisions the design document must settle

Where it goes live (YouTube, Twitch, an own site only); the LLM and TTS providers and a monthly cost ceiling; how the browser scene is recorded (a headless browser and ffmpeg, or frames rendered server side); how interviews and pundit shows are scripted and grounded; moderation of generated social content.

### Simulation items that feed the broadcast

From the M8 report (`docs/milestones/M8.md`): give tactical style choices their costs and raise their influence again (matches would vary more by manager); let the manager AI batch several substitutions into one stoppage; late-game dynamics so the second half is not thinner than the first (the goal timeline is the largest known calibration gap); the single-match performance budget.

## 4. Design principles that keep these cheap

1. **Everything downstream consumes the event log + summary**, never sim internals.
2. **Additive evolution:** new optional fields/event types = minor schema bump; golden tests are per `(SIM_VERSION, model_profile)`.
3. **Behaviour in data wherever possible** (roles, traits, formations, injury types, mood kinds, development curves in YAML validated by Pydantic).
4. **Every tunable is a named config value** with a documented effect and a sensitivity report (02 §14.6).
5. **Determinism is a feature, not a constraint**: replays, audits, learning environments and regression tests all rely on it.
