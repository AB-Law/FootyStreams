# 07 — World Systems: Calendar, Mood, Development, Contracts, Transfers

Status: **PROPOSED (Phase 1, revision 2).** Added after review: transfers and player development are **in scope**; cup play, youth *competitions*, loans and promotion/relegation are out (schemas reserve them). All of this lives in the `league` layer (never in `sim`) and obeys the same determinism rules: every random draw comes from a named `SimRng` stream.

## 1. In-world time

- The world advances **one day at a time** through `WorldClock.advance_day()`. A fixed, ordered **daily tick pipeline** runs (§2). Matches are played on matchdays; the sim itself is untouched by the tick.
- Season shape (all configurable in `LeagueCalendarConfig`): preseason window → 14 matchdays at 7-day spacing (weekly cadence: "a bad week" is a meaningful unit) → a short **mid-season transfer window** after matchday 7 → season end → **off-season block** (default 42 in-world days: awards, rollover, progression, expiry, summer window, youth intake) → next season fixtures generated.
- Contracts end on a fixed `contract_end_day` (default June 30 equivalent); transfer windows are explicit date ranges stored in `TransferWindow` rows.
- No wall-clock anywhere. The broadcast layer decides how in-world days map to channel time (e.g. a "midweek magazine" slot covers the days between matchdays).

## 2. Daily tick pipeline (order matters; each stage is a pure function `(WorldReader, date, rng) -> WorldDelta`)

1. **Recovery:** fatigue/fitness/sharpness drift (rest day vs. training), injury healing (`expected_return_on`, medical facility/physio effects), suspension countdown at matchday only.
2. **Training & micro-development:** weekly training increments (§4.2).
3. **Mood:** expire/decay `StateModifier`s; apply deterministic rule-based modifiers from facts (§3.2).
4. **World events:** the seeded `WorldEventGenerator` rolls life events (§3.3).
5. **Contracts:** expiry warnings, renewal negotiations (§5).
6. **Transfers:** (only inside a window) AI clubs analyse, bid, negotiate, complete (§6).
7. **Club admin:** wage accrual (weekly), sponsorship/broadcast instalments, debt interest, board confidence update.
8. **Matchday:** if fixtures today → `league.setup.build_match_setup` → `sim` → `post_match.derive_world_delta` → apply (one transaction per match).

Idempotency: each stage writes a `world_log` row `(date, stage, delta_hash)`; re-running a day with the same seed is a no-op/verifiable.

## 3. Mood, life events and "the week they had"

**Requirement:** things that happen around the world — a media storm, a row with the manager, a transfer snub, a personal matter, a new contract, a derby hero moment — should show up on the pitch. A star having a terrible week can look merely average; a player with a good week can punch above his weight. The sim stays a pure function: the effect is computed **before** the match and frozen into the `PlayerSnapshot`.

### 3.1 Entities

```
StateModifier
  id, owner: EntityRef (player|manager|referee)           # referee/manager use limited effect set
  kind: StateKind                                         # see below
  magnitude: Unit                                         # severity/strength of the underlying cause
  start_on: GameDate;  expires_on: GameDate | None
  decay: linear | half_life(days)
  source: {origin: rule | world_event | proposed, world_event_id | None, proposal_id | None, match_id | None, event_ids}
  visibility: public | private                            # may a commentator mention it?
  summary_key: str                                        # deterministic template key ("row_with_manager"), not prose
  rev

StateKind (v1): personal_turmoil, family_matter, media_storm, dressing_room_row, manager_row,
   contract_dispute, transfer_unrest, transfer_snub, homesickness, fan_abuse, blamed_for_defeat,
   dropped_unfairly, injury_return_joy, new_contract_glow, award_glow, derby_hero, trophy_glow,
   manager_backing, new_signing_enthusiasm, captaincy_pride, rested_and_happy, confidence_surge

WorldEvent                                                 # a record of "something happened in the world"
  id, date, kind (e.g. transfer_completed, contract_signed, bust_up, media_story, award, long_injury, retirement,
                  record_broken, rumour_started), participants: list[EntityRef], facts: dict (typed per kind),
  visibility: public|private, origin: rule | generator | proposed
```

`WorldEvent` is the shared "news feed" that the LLM layer will later narrate and index into memories; `StateModifier`s cite the event that caused them.

### 3.2 Who can create modifiers

| Source | Examples | Notes |
|--------|----------|-------|
| **Deterministic rules from facts** (post-match, daily) | error leading to a goal → `blamed_for_defeat`; dropped after being promised starts → `dropped_unfairly`; unsold after transfer request → `transfer_unrest`; scored winner in derby → `derby_hero`; returns from long injury → `injury_return_joy` | Always on. Magnitude from the fact's size and personality (`ego`, `resilience`). |
| **Seeded WorldEventGenerator** | Life events with per-player daily hazard scaled by personality (`volatility`, `media_openness`, `sociability`…): media story, manager row, personal matter | Pure RNG stream `world_events:<date>`; rates configurable; the "things happening around the world" without an LLM. |
| **LLM proposals (future)** | A press conference exchange escalates; a generated story about a feud | `CreateStateModifier` proposal; see bounds below. |

### 3.3 Resolving mood for a match (pure)

`resolve_mood(player, date, personality, active_modifiers, config) -> ResolvedMood`

1. For each active modifier: `strength_i = magnitude × decay(date) × sensitivity(kind, personality)` where sensitivity uses e.g. `resilience`, `professionalism` (shrink negative effects), `ego`/`volatility` (amplify row/snub kinds), `loyalty` (amplifies transfer kinds), `media_openness` (media storm).
2. Each kind maps to effect weights on three multipliers: `mental`, `technical`, `physical` (e.g. `personal_turmoil`: mental −1.0, technical −0.5, physical −0.15; `derby_hero`: mental +0.6, technical +0.3) plus `volatility_add` (dissent/foul risk) and `big_match_shift`.
3. Combine negatives as `1 − Π(1 − e_i)` (diminishing stacking), positives likewise, then net and **clamp to hard caps** from `MoodConfig`: default max penalty **−20% mental, −10% technical, −5% physical**; max bonus **+6% mental, +3% technical, +1% physical**. Asymmetric on purpose: collapsing is easier than over-performing. Effective magnitude of a star's bad spell ≈ 8–15 rating points on the mental block and ~5–8 on the technical composite, i.e. a top player looks league-average, as intended.
4. Output `ResolvedMood{mental_mult, technical_mult, physical_mult, volatility_add, contributing_modifier_ids, public_storyline_keys}` is copied into `PlayerSnapshot.mood`. The sim applies it as the single extra modifier `M_state` in the effective-attribute formula (02 §3). The match record stores the snapshot, so a match is replayable and auditable even if modifiers later change.
5. `public_storyline_keys` (only `visibility=public` modifiers) are put in the kickoff preamble (`PlayerPreamble.storylines`), so a future narrator can say "he's had a difficult week" without learning private details. Private modifiers influence the pitch but are never exposed in events.

### 3.4 Bounds on LLM-originated modifiers (enforced by the future applier; schema and validator exist now)

- `kind` must be in a whitelist; `magnitude ≤ 0.5 × deterministic cap` for that kind; at most **one** proposed modifier per entity per 7 in-world days and a global per-day budget;
- must cite an existing `world_event_id`, `match_id/event_ids`, or `memory_id` that involves the owner;
- cannot target attributes directly, only the three multipliers through `StateKind`;
- all proposed modifiers are logged in `proposals` with accept/reject reason; the hard caps in §3.3 apply to the *sum* of all sources.

This answers "should the LLM-world affect the pitch?" with **yes, through a narrow, auditable door**: facts and generator events do most of the work, the LLM adds colour and escalation, and nothing it produces can exceed the hard caps or change anything it cannot cite.

### 3.5 Morale vs. state modifiers

`morale` (0–1 slow-moving scalar, ±3%) remains the "background mood" driven by results/playing time. `StateModifier`s are discrete, explainable, time-limited episodes with larger (capped) effects. Morale factors on the Player are kept as a derived summary list of the *reasons*.

## 4. Player development

### 4.1 Model

Attributes change; `ability_current` is recomputed from them; `ability_potential` (PA) is the hidden ceiling (and is itself occasionally revised for young players). Changes arrive in two ways:

- **Weekly micro-steps** during the season (small training + match-experience increments, accumulated as fractional "progress points" per attribute and applied when ≥ 1.0, so deltas are integers and the journal is readable).
- **Season-end progression** (big step during the off-season block): age curve, playing time, coaching, facilities, injuries, hidden `development_rate`.

### 4.2 Per-attribute change

```
Δ_a = g(age, group) · headroom(PA, CA) · (0.4 + 0.6·training_quality) · dev_rate · (0.7 + 0.3·playing_time_factor) · prof_factor
      − d(age, group, natural_fitness) − injury_setback_a + noise_a
```

- **Age curves per group** (data-driven in `development.yaml`): physical peaks ≈ 24–27 and declines from ≈ 28 (pace/acceleration first, stamina later, slowed by `natural_fitness`); technical grows to ≈ 28–30, declines slowly after 31; mental grows until ≈ 31–33; goalkeeping peaks later (≈ 28–33). Young players below ≈ 21 have large `g`.
- `headroom = max(0, PA − CA)/PA` — progress slows as a player approaches PA; total ability never exceeds PA (hard cap by scaling the proposed deltas), PA ≥ CA always holds.
- `training_quality` from club `facilities.training`, the staff's coaching attributes matching the attribute group (`coaching_technical/mental/physical`, GK coach for GK attrs), manager `man_management/youth_development` (youth) and the player's training focus.
- `playing_time_factor` from minutes share in the last 10 matches (young players need to play).
- `prof_factor` from `professionalism`; **severe injuries** cause setbacks (physical −0..3) scaled by `injury_proneness`.
- **Position competence** grows when a player is retrained/plays out of position (`versatility`), decays slowly when unused; **role familiarity** grows with use.
- **Traits** can be learned (low probability, youth) or lost.
- **Breakthrough/stagnation:** with small probability a player aged 17–23 gets a PA revision (+3..+8 / −3..−8) — deliberately noisy so scouting judgement matters.
- Positions: `GK` stays GK; outfield `primary_position` is re-derived.

### 4.3 Youth intake, retirement, free-agent pool

- Each academy produces `intake_size` prospects per off-season (generated by the same player generator with academy level/quality shaping CA/PA; names from the nation mix) → `squad_status=youth`, contract 3 years.
- **Promotion** of youth to the senior squad is an AI decision (ability vs. squad gap) — youth *matches* are out of scope.
- **Retirement:** probability by age (from ≈ 33), ability and role; retired players leave the pool (`status=retired`, kept for history). Squad rebalancing keeps senior squads in 22–28.
- **Free agents** pool persists across seasons; the generator tops it up with plausible journeymen so signings are always possible.

### 4.4 Targets (tested; see §8)

League-average CA stays within ±1.5 over 20 seasons (no inflation/deflation); mean peak age of CA ≈ 26–29; players with PA ≥ 85 reach ≥ 92% of PA by 27 on average; average 17-year-old CA ≈ 40–50% of the league senior mean; 5–9% of senior players retire per season; youth intake keeps squad ages stable (league mean age 25.5–27.5).

## 5. Contracts

- Fields (01 §1.6) become **L**: wage, start/end, bonuses (appearance/goal/clean sheet applied via ledger on post-match), release clause (can trigger a transfer), sell-on, squad role (playing-time promise → mood when broken).
- **Renewals:** AI manager/board open talks when ≤ 12 months remain (priority by importance in `squad_role`). Player willingness: `willing = f(wage_offer/market_wage, club_reputation vs. ambition, promised role vs. expectation, loyalty, mood, relationship with manager)`; counter-offers up to 3 rounds; failure → player runs down contract (mood modifier `contract_dispute`), becomes free agent at expiry.
- Wage structure constraint: wage ≤ club `wage_budget_weekly` share; squad wage bill must satisfy the board's `budget_strictness` or the club sells.
- Termination (release with pay-off) = ledger entry, reserved for sacking decisions.

## 6. Transfers

### 6.1 Entities (all **L**; tables in 04 §4.1)

```
TransferWindow    {id, season_id, kind: summer|midseason, opens_on, closes_on}
TransferListing   {id, player_id, club_id, asking_price, reason: surplus|financial|player_request|released, status, listed_on}
TransferBid       {id, window_id, player_id, from_club_id|OUTSIDE_WORLD, to_club_id|OUTSIDE_WORLD, fee: Money, installments: list,
                   sell_on_pct, status: open|countered|accepted|rejected|withdrawn|expired, round: 1..3, expires_on, created_on, parent_bid_id}
ContractOffer     {id, bid_id|None, player_id, club_id, wage_weekly, length_years, bonuses, role_promise, status, round}
Transfer          {id, bid_id, player_id, from, to, fee, completed_on, medical: passed|failed|skipped, contract_id}
ScoutReport       {id, club_id, scout_id, player_id, perceived_ability (noisy), perceived_potential (noisier), confidence, created_on}   # R: drives AI shortlists now internally; stored later
OUTSIDE_WORLD     # synthetic counterparty representing every club outside the 8-club league
```

### 6.2 AI club behaviour (`league/transfer_ai.py`, pure given RNG stream `transfers:<window_id>`)

1. **Needs analysis:** squad coverage per formation slot (depth chart by `position_competence` and role fit), age profile, quality gap vs. starters, injuries, contracts expiring. Output `Need{position, urgency, min_quality, max_age, budget_share}`.
2. **Shortlisting:** candidates from other league clubs (listed or not), free agents, and the **OUTSIDE_WORLD** market (a generated supply of players refreshed each window, sized so the league economy neither starves nor floods). *Perceived* ability = true ability + noise `σ = 12·(1 − scout_judgement/100)` (the board/manager's `judging_ability`, scouts' `scouting_judgement`), so clubs sometimes overpay or miss gems. Filters: budget (fee + wages vs. `transfer_budget`/`wage_budget`), player willingness to join (§5 logic: reputation, ambition, role promise, wage), age/ability fit.
3. **Valuation & bidding:** `bid = market_value × (1 + desire·Δ + urgency·0.4 + noise)`; seller's reservation price = `max(market_value × stubbornness_factor, listing asking)`, higher for key players, lower if `transfer_unrest`/financial pressure; up to 3 negotiation rounds, accept if `bid ≥ reservation × (0.9..1.0)`.
4. **Player terms:** after a club–club agreement, `ContractOffer` negotiation (≤ 3 rounds); medical (probability of failure from `injury_proneness`/current injury).
5. **Sales logic:** surplus (squad > 28, depth), unhappy (`transfer_unrest`/request), financial need (balance < threshold, debt covenants — Boom & Bust), and **OUTSIDE_WORLD bids** that arrive stochastically for top-quality/high-PA players (rate scales with reputation).
6. **Completion:** atomic delta: contract replaced, squad entries updated, **ledger entries** (buyer `transfer_fees` expense, seller `player_sales` income, agent/other fees optional; league-internal transfers net to zero in the closed system; OUTSIDE_WORLD legs are the only open flows and are tracked in a dedicated `world_balance` ledger), `WorldEvent(transfer_completed)`, mood modifiers (`new_signing_enthusiasm` on buyer's player; `transfer_unrest` for rejected requests), relationship edits (friends left behind — R), and `Memory` facts later (when memory logic exists).
7. **Deadline behaviour:** urgency increases over the window; clubs below minimum squad size or lacking a GK panic-buy (free agents first). End-of-window invariant: every club has ≥ 22 senior players, ≥ 2 GKs, formation coverage ≥ 1 player per slot.

### 6.3 Finance interplay

`transfer_budget` is replenished by the board at season rollover (function of prior profit, reputation, owner investment) and by sales income. Wage bill ≤ `wage_budget`. Debt service and insolvency pressure (negative balance beyond `credit_limit`) force sales and, in extreme cases, a points deduction (R). The closed-system ledger invariant: `Σ league balances + world_balance = constant + Σ declared external flows` (sponsorship/broadcast inflows from "outside", wages to people — modelled as flows to the world — so the test checks *per-club* balance integrity, *per-transfer* leg symmetry, and the closed-system identity with declared external accounts).

## 7. Season rollover (off-season block) — ordered steps

1. Final standings, tie-break resolution, prize money, awards (`WorldEvent`s: champion, top scorer, player of the season via season-average ratings).
2. Club history (`SeasonRecord`), reputation updates (results vs. expectation, bounded), fanbase size drift, board confidence vs. objectives, manager contract/`manager_confidence` (sacking/appointment are **schema only for now**, decision O1 in 09).
3. Contract expiry → free agents; renewals already attempted.
4. Retirements; squad shrink/regrow rules.
5. Season-end progression (§4); recompute `ability_current`, `market_value`, positions, role ratings.
6. Youth intake; promotion decisions.
7. Summer transfer window (§6) run day by day.
8. Finance rollover (budgets, sponsorship renewals, wage inflation).
9. New season: fixtures regenerated (home/away balanced vs. last season), weather seeds, calendar.

## 8. Balance targets for world systems (statistical, tier "slow")

| Area | Target |
|------|--------|
| Economy (20 seasons) | League wage/income ratio 55–75%; ≤ 1 club in sustained distress; no hyperinflation (market value of a 75-CA 26-year-old within ±30% of season 1 after inflation parameter) |
| Transfers per window | 6–14 league-internal + 3–8 with OUTSIDE_WORLD (summer), 2–6 total (mid-season) |
| Fees | mean fee/market_value 0.95–1.25; top fee ≤ 3× the richest club's transfer budget |
| Squads | 22–28 senior at all times after window close; every formation coverable |
| Parity (30 seasons) | Giants win 30–50% of titles; no single club > 60%; every club wins ≥ 1 title in ≥ 20% of 30-season runs; relegation-less so bottom club finishes bottom ≤ 40% |
| Development | see §4.4 |
| Mood | In a 200-match test, matches with an active ≥ 0.15 negative mood on a starter show a mean −0.04…−0.10 goal-difference effect vs. matched controls (the effect exists but is not decisive) |

All thresholds are editable in `data/static/balance_targets.yaml` (02 §14.6).

## 9. Tests (summary; detail in 06)

Determinism of a multi-season run (hash of standings + ledger + squads after N seasons); development monotonic limits (CA ≤ PA; age curve shape); transfer atomicity (failure mid-transfer rolls back); ledger identities; squad-constraint invariants at window close; mood clamps (property test: any modifier set stays within caps); LLM-modifier validator rejects over-cap/uncited/over-rate proposals; `resolve_mood` is pure (same inputs ⇒ same output).
