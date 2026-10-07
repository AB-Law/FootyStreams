# FootyStreams — Phase 1 Design (revision 3)

A fictional football league as a 24/7 live broadcast. This phase builds the **foundation**: a rich data model, a deterministic match simulation, a typed event stream, and the world systems (mood, development, contracts, transfers) that keep a multi-season league alive. Commentary (LLM), TTS, rendering, memory logic and any server come later and plug into the seams defined here.

**Status: PROPOSED — all decisions in [09](09-schema-decisions.md) are now locked; awaiting your go-ahead for Phase 2. No implementation code exists yet.**

| Doc | Contents |
|-----|----------|
| [01-entities.md](01-entities.md) | Schemas for Player, Manager, Club (stadium, fanbase, finance, board, academy, staff), Referee, Commentators/Media, Competition/Season/Fixture, Match/TeamSheet/Weather, Relationship, Memory, plus world-state entities (§11). Every field tagged **S**im / **L**eague / **R**eserved. |
| [02-simulation.md](02-simulation.md) | How attributes, tactics, roles, fatigue, mood, referee, weather and stadium feed the match model; spatial/possession model; home advantage; AI manager; determinism; **balance targets, profiles and tuning (§14)**. |
| [03-events.md](03-events.md) | The discriminated event union (incl. opt-in `frame`), commentary context, sequencing rules, summary/ratings, analytics-ready stats, schema export. |
| [04-architecture.md](04-architecture.md) | Layering, package layout, pure-sim boundary, persistence (relational + JSON documents; ground truth vs LLM proposals), repository ports, extension Protocols incl. `ManagerPolicy`. |
| [05-seeding.md](05-seeding.md) | The 8-club world, archetypes, generators, name cultures, coherence checks, world-systems seed data. |
| [06-milestones.md](06-milestones.md) | M0–M14, what runs at the end of each, **PR slices per milestone**, and the cross-cutting test plan. |
| [07-world-systems.md](07-world-systems.md) | **New.** Calendar and daily tick, **mood/life events ("a bad week shows on the pitch")**, player development, contracts, transfers (incl. outside-world market), season rollover, targets. |
| [08-roadmap.md](08-roadmap.md) | **New.** Future scope and the hooks built now: gegenpressing/triangles/pass maps/xG/frame data, **learning AI managers**, cup play, youth teams, loans, LLM layers. |
| [09-schema-decisions.md](09-schema-decisions.md) | Decision log: everything is locked (L1–L30 + four resolved items); two small open items (O5 TTS provider, O6 GitHub remote). |
| [10-testing-strategy.md](10-testing-strategy.md) | **New.** 17 test types, tiers T0–T3, 11 e2e scenarios, edge cases, single invariant catalogue, mutation/perf/soak/chaos, **operational safety for a live 24/7 channel**. |
| [11-engineering-standards.md](11-engineering-standards.md) | **New.** Clean-code limits, SOLID and DRY made concrete, performance budgets, **change-fragment log and release notes**, review checklist, AI-agent rules, **git workflow, agent rules + end-of-turn gate**. |
| [12-voice-and-tts.md](12-voice-and-tts.md) | **New (rev 4).** What makes commentary sound human, `VoiceProfile v2` / `VoiceSynthesizer v2`, provider landscape, bake-off plan. |
| [13-runtime-engine.md](13-runtime-engine.md) | **New (rev 4).** The long-running engine: supervisor, pre-simulation buffer, paced match player, event bus/sinks, crash-only resume, health. |
| [.claude/rules/](../../.claude/rules/core.md) | **New (rev 4).** Agent rules for Claude Code (`.claude/rules/`) and Cursor (`.cursor/rules/`). |

Root files: [`AGENTS.md`](../../AGENTS.md) / `CLAUDE.md` (rules for agents), [`CHANGELOG.md`](../../CHANGELOG.md) and [`changes/`](../../changes/README.md) (the change log).

## What changed in revision 2 (from your review)

1. **Pass-level events**, **cross-platform determinism**: confirmed and locked.
2. **Persistence clarified:** it is SQL, not NoSQL. Anything you sort/filter by (matches, matchdays, dates, scores, event type/time, stats, ledger) is a real indexed column; only deeply nested structure lives in JSON, with promote-to-column and SQLite generated-column escape hatches (04 §4.1).
3. **"A bad week shows on the pitch"** is now a first-class system (07 §3): `StateModifier`s from deterministic rules, a seeded world-event generator, and (future) bounded LLM proposals are resolved into a `ResolvedMood` frozen into the match snapshot. A star's collapse is capped (default −20% mental / −10% technical / −5% physical), so he can look merely average; the sim stays pure and replayable. Public episodes surface as storyline keys the commentary layer can mention; private ones affect play silently.
4. **Transfers and player development are in scope** (07 §4–§7): age curves per attribute group, potential/headroom, coaching/facilities/playing-time effects, retirement, youth intake, contract renewals/expiry, transfer windows, AI clubs with noisy scouting, negotiations, a synthetic outside-world market, and a closed-system ledger. Milestones M10–M11 added.
5. **Balance targets are tunable** (02 §14): profile-based YAML (`realistic`, `high_scoring`, `defensive_grind`, `chaos`), every behaviour a named `SimConfig` knob, `balance sensitivity` and `balance fit` tools. The default numbers are my recollection of typical top-flight averages, not a dataset I looked up (stated in the doc).
6. **Match model growth path** recorded (08): sim built from swappable components (`PositioningModel`, `DecisionModel`, `PressModel`, `ShotQualityModel`, …) selected by `model_profile`; `frame` tracking events, pass matrices, shot maps, xG/xA/xT are in the schema now so gegenpressing, passing triangles and pass maps are extensions rather than rewrites.
7. **Learning AI managers** noted as future scope with seams in place now: `ManagerPolicy` Protocol, `policy_id` on every team sheet, reserved `manager_knowledge` table, and the sim as a fast deterministic training environment (08 §2).

## What changed in revision 3 (reliability, quality, performance, change log)

1. **Testing** ([10](10-testing-strategy.md)): unit, property, metamorphic, contract, integration, **end-to-end** (11 subprocess scenarios incl. full season, multi-season, replay, crash recovery, upgrade, schema contract, broadcast rehearsal), golden, determinism matrix (Windows/Linux, Python 3.12/3.13), statistical, performance, **soak** (50–200 seasons), **fuzz/chaos/fault injection**, **mutation testing**, doc tests. Four tiers: T0 < 60 s per commit, T1 ≤ 10 min per PR, T2 nightly, T3 release gate with a 7-virtual-day shadow run.
2. **"Nothing may break on air"** is a design requirement, not just tests: matches are simulated ahead of airtime, every match passes a production **pre-air verification gate** (the same `verify/` code the tests use), failures are quarantined with a fallback path, stages are idempotent, migrations back up first, side-layers (commentary/voice) can never block or alter the event stream.
3. **Clean code, SOLID, DRY** ([11](11-engineering-standards.md)): limits enforced by tooling (complexity ≤ 8, ≤ 5 params, no magic numbers, no flag args, strict types, docstrings), SOLID mapped to specific structures (data-driven roles/traits, Protocol seams, shared contract suites, composition root), DRY via single sources of truth (models → schemas, one invariant catalogue, generic JSON repository), counterbalanced by the rule of three to avoid over-abstraction.
4. **Performance** is budgeted and tested (match ≤ 150 ms mean incl. validation; season ≤ 12 s on 4 workers via matchday-parallel simulation), with hardware-independent op-count assertions and a "no optimisation without a benchmark" rule.
5. **Change log**: one fragment file per change in `changes/unreleased/` → generated `CHANGELOG.md` and `release-notes/vX.Y.Z.md` + `.json`; plus `docs/status.md` and per-milestone reports, and `AGENTS.md`/`CLAUDE.md` so Cursor/Claude start from the right context. Already started for the design phase.
6. Milestones with a quality gate at the end of each (now M0–M14 after revision 4); test/quality infrastructure and the changelog tool land in M0, hardening and the release gate in M14.

## What changed in revision 4 (your review of entities, architecture and standards)

1. **Attributes vs "Rating"** (01 §0.2, §1.9): the single shared `Rating` alias is gone. Players *are* defined by ~50 independent attributes (that is how each is good at different things); the alias only meant "a 0–100 number", which was misleading, so it is now split into `Attribute`, `Competence`, `Reputation`, `Disposition`, `Level`, `AbilityScore`. New derived **`PlayerProfile`** (role ratings, strengths/weaknesses, signature skills, archetype label) so nothing collapses into one number; the generator makes spiky profiles.
2. **Tactics are extensible** (01 §3.8): versioned core + registry of tactic modules (v1 modules implemented; gegenpress, support geometry/triangles, overloads, rest defence, positional zones, named set-piece routines, individual tendencies pre-stubbed), per-phase shapes, per-player instructions, situational plans, namespaced extensions, read through a `TacticsView`.
3. **Voice** (12): `VoiceProfile v2` (casting sheet + provider bindings + lexicon) and a capability-aware `VoiceSynthesizer v2`; what makes commentary sound human (script style, interjections/overlaps, pronunciation, mastering, pre-rendering); provider landscape and a bake-off to choose — **no provider is chosen yet**.
4. **Engine, not CLI** (13, 04): the product is `uv run engine` — a supervised, crash-only, forever-running service that keeps a pre-simulated buffer ahead of airtime, replays verified matches at broadcast pace, and feeds sinks. CLIs remain as thin dev/ops tools. New milestone M12.
5. **Claude and Cursor rules + end-of-turn gate** (11 §11): rules in `.claude/rules/` with a plain copy in `.cursor/rules/`; a Stop hook runs ruff, mypy, tests and the other T0 checks after every agent turn and does not let the turn end until they all pass (skips when nothing changed; loud give-up after 8 consecutive failures to avoid infinite loops). Already installed and tested; it is a no-op until `pyproject.toml` exists in M0.
6. **Git workflow** (11 §12, 06): short-lived branches, atomic Conventional Commits, PRs ≤ 400 lines (cap 800) with a template, rebase-and-merge, and a **PR slice plan for every milestone** so nothing arrives as one huge PR.

## Key decisions at a glance

1. **Pure, restricted-math simulation** with isolated RNG sub-streams; byte-identical logs across Windows/Linux.
2. **Hybrid positional/possession model**, ~1,000–1,400 events/match each carrying `significance`; optional `frame` tracking events.
3. **Attributes are truth; ability is a cache;** every schema number enters the sim through a named, bounded modifier (form, morale, **mood state**, sharpness, energy, competence, role, day-form, context).
4. **Events are causal and self-describing;** hindsight facts only in `fulltime`/summary and a separate annotation pass.
5. **Relational SQL + validated JSON documents** behind repository Protocols; one transaction per match; one per daily tick stage.
6. **LLM boundary = proposals:** no write path to ground truth; bounded, cited, rate-limited proposals for memories, relationships and mood modifiers.
7. **World is generated** (8 archetype-driven clubs, ~264 players, invented name cultures, authored-archetype commentators) and then **lives**: daily tick, mood, development, contracts, transfers, rollover.
8. **Everything tunable:** targets, sim knobs, mood caps, development curves, transfer constants are data.

## Open items: none blocking (two small ones tracked: TTS provider → bake-off later; GitHub remote → M0)

All four have been decided ([09](09-schema-decisions.md)): manager sack/hire is schema-only for now; synthetic outside-world transfer market is in; mood caps −20/−10/−5 (bonuses +6/+3/+1); `frame` events default to 1 s cadence when enabled, for smooth rendering, without ever affecting other events.

## Defaults retained (veto any)

Attribute scale 1–100; money in whole "crowns"; 8 clubs, double round robin (56 matches/season); 5 subs in 3 windows + half-time; video review optional (M12); no cup play, youth competitions, loans or promotion/relegation yet; package `footystreams`; `typer` CLI; async Protocols for Narrator/MemoryUpdater/VoiceSynthesizer.

## What happens next

On your answers to the four open items (or "use recommendations"), Phase 2 starts at **M0** and proceeds milestone by milestone, running tests and the CLI and reporting after each.
