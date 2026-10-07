# 09 — Schema Decision Log

Purpose: "full schema now" means every decision that shapes a model or contract is made **before** M1, so the schemas in `schemas/` are stable. Each decision is **LOCKED** (decided by you or by a default you accepted) or **OPEN** (needs your answer — recommendation given). Update this file whenever a decision changes; any change after M1 requires a schema version bump.

## Locked

| # | Decision | Source |
|---|----------|--------|
| L1 | Pass-level events (≈ 1,000–1,400/match) with `significance` for filtering | You (Q1) |
| L2 | Byte-identical determinism across Windows and Linux (exact-arithmetic sim core, own RNG) | You (Q2) |
| L3 | Persistence = relational SQL (SQLite via SQLAlchemy) with real columns for everything sortable + validated JSON documents for nested structure; promote-to-column / generated-column escape hatches | You (Q3), clarified in 04 §4.1 |
| L4 | LLM/world-event influence on performance is allowed **through bounded, cited, rate-limited `StateModifier`s** resolved into the snapshot before the match; hard caps (default −20% mental / −10% technical / −5% physical; +6/+3/+1) | You (Q4); numbers = my default, see O3 |
| L5 | Full schema up front; reserved (R) fields are tagged and tested by the usage registry | You (Q5) |
| L6 | Attribute scale 1–100; money = int "crowns"; weekly wages; 8 clubs, double round robin (56 matches/season); 5 subs in 3 windows + HT; 90-min matches; no extra time/shootouts; video review optional (M13) | Defaults accepted |
| L7 | **Transfers and player development are in scope** (07). Cup play, youth competitions, loans, promotion/relegation are future scope with schemas reserved | You |
| L8 | Balance targets are **profile-based and tunable** (`balance_targets.yaml`, `--profile`, sensitivity, fit); default `realistic` | You |
| L9 | The sim is built from Protocol-typed components selected by `model_profile`, so gegenpress/triangles/pass-maps/frame-data/learning managers extend rather than rewrite (08) | You |
| L10 | `frame` tracking events exist in the union from v1.0 (opt-in) | Consequence of L9 |
| L11 | IDs: prefixed lowercase base36 (`plr_0a1b2c`), deterministic from world seed + per-kind counter; event ids `{match_id}:{seq:05d}` | Default |
| L12 | Pitch coordinates absolute (home attacks +x in period 1); match clock excludes half-time | Default |
| L13 | Ability (`ability_current`) is a derived cache; attributes are truth; potential hidden | Default |
| L14 | Memory is schema-only; facts written deterministically, everything else via proposals | Default |
| L15 | Relationships are a separate cross-entity table; memories are a separate table; neither embedded in person rows | Default |
| L16 | Men's league; generated names are fully invented (no real names; deny-list enforced); mixed-gender referees/media/staff; `gender`/`pronouns` fields exist for voice/prose | Default |
| L17 | Daily tick pipeline, weekly matchday spacing, 42-day off-season block, mid-season window after matchday 7 | Default (07 §1) |
| L18 | Learning managers are future scope; `ManagerPolicy` Protocol, `policy_id` on the team sheet, reserved `manager_knowledge` table exist now | You (note), 08 §2 |
| L19 | **Verification is one implementation** (`verify/`), used by tests, `--strict`, soak and the production **pre-air gate**; matches are pre-simulated ahead of airtime; failures are quarantined with fallback (10 §7) | You (reliability requirement) |
| L20 | **Test regime:** 17 test types, tiers T0–T3, 11 e2e scenarios, mutation ≥ 85% on critical modules, coverage floors, no flaky tests tolerated (10) | You |
| L21 | **Engineering standards** are lint-enforced where possible: complexity ≤ 8, ≤ 5 params, no magic numbers, no flag args, SOLID/DRY mapped to structures, rule of three (11) | You (clean code, DRY, SOLID) |
| L22 | **Performance budgets** are tests (match ≤ 150 ms mean incl. validation; season ≤ 12 s on 4 workers; etc.), matchday-parallel simulation, optimisation only with benchmark evidence (11 §6) | You (performance is key) |
| L23 | **Change log** = change fragments (`changes/`) → generated `CHANGELOG.md` + `release-notes/vX.Y.Z.{md,json}`; `docs/status.md` and `docs/milestones/Mx.md` for agent/human context; `AGENTS.md`/`CLAUDE.md` rules (11 §7, §11) | You |
| L24 | Event construction **always validates** by default; trusted construction is only an escape hatch justified by a profile and flagged to you first | Consequence of L1/L22 |

| L25 | **Semantic scale types** instead of one shared `Rating`: `Attribute`, `Competence`, `Reputation`, `Disposition`, `Level`, `AbilityScore`; players are described by ~50 independent attributes plus a derived `PlayerProfile` (role ratings, strengths/weaknesses, signature skills); CA/PA are only summaries; generator produces spiky profiles (01 §0.2, §1.9) | You (review of 01) |
| L26 | **`TeamTactics` is versioned and module-based** (core + registry of tactic modules, per-phase structures, per-player instructions, situational plans, namespaced extensions) so gegenpress/triangles/overloads/routines are additions, read by the sim through a `TacticsView` (01 §3.8) | You (review of 01) |
| L27 | **`VoiceProfile v2`** = provider-agnostic casting sheet + per-provider bindings + pronunciation lexicon; `VoiceSynthesizer v2` is capability-aware and provider-agnostic; **provider choice is deferred to a bake-off in the TTS phase** (12) | You (review of 01) |
| L28 | **The product is a long-running engine** (`uv run engine`, 13); the CLIs are thin dev/ops tools over the same library code; wall clock/asyncio/signals only in `runtime/` | You (review of 04) |
| L29 | **Agent rules** are authored once in `.claude/rules/` (read by Claude Code) and generated into Cursor's `.cursor/rules/*.mdc` format; **end-of-turn Stop hook** runs `uv run check` and blocks until it passes completely (retry cap with loud give-up) (11 §11) | You |
| L30 | **Git workflow:** trunk-based short-lived branches, atomic Conventional Commits, small PRs (≤ 400 lines, cap 800), PR template, rebase-and-merge, per-milestone PR slice plan; agents never merge/push `main`/force-push shared branches (11 §12, 06) | You |

| L31 | **Human review checkpoint before any push or PR:** agents commit locally, present a review package, and wait for the owner's explicit go-ahead; approvals do not carry over between slices; applies to the first push to the empty remote too (11 §12) | You |
| L32 | Remote repository: `https://github.com/AB-Law/FootyStreams` (public, currently empty) | You |

## Previously open — now decided

| # | Decision | Outcome |
|---|----------|---------|
| O1 | Manager sackings/appointments | **Schema only.** Board confidence, objectives, manager contracts and the 4-manager free pool exist; no sack/hire logic yet (managers are stable across seasons for now). Revisit with learning managers (08 §2). |
| O2 | Outside-world transfer market | **Yes, synthetic `OUTSIDE_WORLD` counterparty** (07 §6). |
| O3 | Mood caps | **−20% mental / −10% technical / −5% physical; +6/+3/+1** (`mood.yaml`, tunable). |
| O4 | `frame` cadence | **1 s of match time by default when frames are enabled** ("I want it to look smooth"). ≈ 5,500 frames × 23 entities ≈ 5–8 MB JSON/match (≈ 0.5 MB gzipped; NDJSON frames can be written to a side file). The sim's positional layer still updates every 4 s; frames are produced by deterministic interpolation of player targets and of the ball between event positions/durations (no RNG draw), so **enabling frames never changes any non-frame event** (an invariant test compares logs with frames on/off). Configurable (`--frame-interval 0.5|1|2|4`). |

## Still open (not blocking Phase 2)

| # | Question | Recommendation |
|---|----------|----------------|
| O5 | **TTS provider(s)** for the voice phase | Decide in the bake-off (12 §5), not now. Phase 2 only builds the abstraction. |
| O6 | ~~GitHub remote~~ **Resolved:** `https://github.com/AB-Law/FootyStreams` (public, empty). Note it is **public**: design docs, code and history will be visible. Say if you'd rather make it private before the first push. | — |

## Resolved details inside the docs worth knowing (not asking, just listing)

- Reserved event types: `shootout_kick`, `extra_time_start`, `weather_change`, `crowd_reaction`, `manager_reaction`, `var_check_started`.
- `OUTSIDE_WORLD` is a reserved club row (`clb_outside`) for FK integrity.
- `StateModifier.visibility = private` influences play but never appears in events; `public` ones surface as preamble `storylines` keys only.
- Every `PlayerSnapshot` embeds the resolved mood and the match stores the snapshot → replay is exact regardless of later world changes.
- Targets in 02 §14 are from general knowledge of top-flight averages, not a looked-up dataset; they are defaults to be tuned, not claims.
