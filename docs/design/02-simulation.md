# 02 — Simulation Design

Status: **PROPOSED (Phase 1).**
Entry point: `simulate_match(setup: MatchSetup, seed: int, config: SimConfig) -> Iterator[MatchEvent]` (plus a `run_match()` wrapper returning `MatchResult{events, summary, setup_ref, seed, sim_version, config_hash, log_digest}` — no sim-internal `end_state`). Pure: no I/O, no clock, no global state, no logging, no `numpy`.

## 1. Guarantees and what "pure" means here

| Guarantee | Mechanism |
|-----------|-----------|
| Same `(setup, seed, config)` ⇒ same event log **byte for byte** | Own RNG class (§13), canonical JSON serialisation, stable iteration order (lists/sorted keys only), float rounding at emit time, golden-file tests. |
| No global random state / wall-clock | `import random` and `time`/`datetime.now` are banned inside `footystreams/sim` by an AST test; the only randomness source is a `SimRng` instance created in `simulate_match` and passed explicitly to every function that needs it. |
| Stream isolation | The master seed forks named sub-streams (`play`, `discipline`, `injury`, `setpiece`, `mgr_home`, `mgr_away`, `dayform`, `review`). Re-tuning the injury model does not reshuffle who scores. |
| Cross-platform reproducibility | The sim core restricts itself to IEEE-754 exact operations (`+ − × ÷ sqrt`, comparisons). No `exp/log/sin/cos/atan/pow(float)` (these are libm-dependent). Sigmoids/normals are replaced by algebraic equivalents (§13). Enforced by a test scanning the package AST. |
| Monotone clock | `t` (elapsed seconds) never decreases; `seq` strictly increases. |

## 2. Inputs and static tables

> **Tactics access (revision 4):** sim components never read `TeamTactics` storage directly; they read a `TacticsView` (`view.pressing.intensity`, `view.defensive_block.line_height`, …) that supplies module defaults when a module is absent. This keeps the sim stable while tactic modules are added (01 §3.8).

`MatchSetup{match_id, home: TeamSheet, away: TeamSheet, referee: RefereeSnapshot, weather, attendance, is_derby, importance, rules: MatchRules, storylines}`. Static content (versioned, loaded once outside the sim and passed in via `SimContext`): formations, roles, traits, injury types.

- **Formation** = 11 slots `{slot, position, base_x, base_y}` in attack-normalised coordinates (own goal x=0). Eight shipped: 4-4-2, 4-3-3, 4-2-3-1, 4-1-4-1, 3-5-2, 5-3-2, 3-4-3, 4-4-1-1.
- **Role** (≈30; e.g. `keeper_classic`, `keeper_sweeper`, `stopper_cb`, `cover_cb`, `ball_playing_cb`, `fullback_holding`, `fullback_overlap`, `fullback_inverted`, `wingback_attacking`, `anchor`, `ball_winner`, `deep_creator`, `shuttler`, `conductor`, `half_space_runner`, `winger_classic`, `winger_inverted`, `inside_forward`, `shadow_striker`, `poacher`, `target_forward`, `pressing_forward`, `drop_in_striker`, `complete_forward`) × duty (`defend/support/attack`). Each role/duty defines:
  - `attr_weights`: which attributes matter for the *role rating* (used by AI lineup picking and ability cache);
  - `offset_in[phase]`, `offset_out[phase]`: positional offsets (dx, dy) relative to the formation slot;
  - `freedom`: how far (metres) the player may roam from his target;
  - `bias`: multipliers on action utilities (`pass_forward`, `pass_lateral`, `dribble`, `shoot`, `cross`, `long_ball`, `carry`), `press_role` (`leader|follower|holder`), `aerial_target` (set-piece role).

## 3. Effective attributes (how the schema feeds the model)

For each player and each decision the sim uses an **effective attribute**:

```
eff(a) = base(a) × M_form × M_morale × M_state(group) × M_sharp × M_energy(a) × M_comp × M_role × M_day × M_ctx(a)
```

| Modifier | Definition | Range | Source fields |
|----------|-----------|-------|---------------|
| `M_form` | `1 + 0.08·(form − 0.5)` | 0.96–1.04 | `form` |
| `M_morale` | `1 + 0.06·(morale − 0.5)` (mental attrs weighted ×1.5, physical ×0.5) | ±3% | `morale` |
| `M_state(group)` | **Life/mood episodes** resolved before the match into `PlayerSnapshot.mood{mental_mult, technical_mult, physical_mult, volatility_add}` (07 §3): a "terrible week" (media storm, manager row, personal matter) can pull a star toward average; a good spell lifts slightly. `group` ∈ mental/technical/physical selects the multiplier; `volatility_add` raises dissent/retaliation foul chance. Hard-capped by `MoodConfig` (default −20% mental / −10% technical / −5% physical; +6% / +3% / +1%). The sim does not know *why*, only the resolved numbers, so the match stays a pure function of its snapshot. | 0.80–1.06 | `PlayerSnapshot.mood` |
| `M_sharp` | `0.97 + 0.03·sharpness` (technical/mental only) | 0.97–1.0 | `match_sharpness` |
| `M_energy(a)` | physical: `1 − k_p·max(0, E_ex)²`; mental: `1 − k_m·max(0, E_ex − 0.4)²`; technical: `1 − k_t·max(0,E_ex−0.2)²` where `E_ex` = in-match exhaustion (§9) | 0.70–1.0 | `fatigue`, `fitness`, `stamina`, `natural_fitness`, `work_rate`, weather |
| `M_comp` | `0.55 + 0.45·position_competence/100` (curved so competence ≥90 → ≈1.0, 50 → 0.78) | 0.55–1.0 | `position_competence[slot_position]` |
| `M_role` | `0.97 + 0.03·role_familiarity/100` | 0.97–1.0 | `role_familiarity` |
| `M_day` | `1 + σ_d·gauss`, `σ_d = 0.012 + 0.05·(1 − consistency/100)`, drawn **once per player per match** from stream `dayform` | ~0.93–1.07 | `consistency` |
| `M_ctx(a)` | crowd/pressure/weather/pitch terms (§8, §10), `big_match` weighted by match importance | 0.9–1.1 | stadium, weather, `big_match`, `leadership` of captain |

Result clamped to `[0.55·base, 1.15·base]` (the lower bound leaves room for stacked fatigue + mood + out-of-position penalties). The key is that **every** schema number touches the model through a named, bounded modifier; none of them can single-handedly blow up an outcome.

**Team cohesion** (`C_team`, 0.97–1.03): `formation_proficiency`, mean `teamwork`, relationship chemistry in the XI (friend/teammate_bond pairs), `culture.discipline`. Applied to pass success and defensive-shape quality.

## 4. Spatial model: how formations and roles change behaviour

The pitch is a continuous 105×68 m plane (normalised 0–1 for events). We do **not** run a physics engine; we run a *positional approximation* that updates all 22 players every `Δt_pos = 4 s` of match time (and on every dead-ball restart), which is cheap and gives coherent geometry.

### 4.1 Target position for a player

```
phase         ∈ {build_up, progression, final_third, transition_att, transition_def, settled_def, press, set_piece}
base          = formation.slot(base_x, base_y)
role_offset   = role.offset[in|out of possession][phase]
line          = tactics.line_height (shifts outfield x by up to ±0.12)
width         = tactics.width        (scales (y − 0.5) by 0.8–1.25)
target        = base + role_offset;  target.x += line_shift(slot_zone); target.y = 0.5 + (target.y−0.5)·width
shift_to_ball = compactness·(ball − target)·(0.12 on x, 0.22 on y)      # team moves as a unit
target       += shift_to_ball
target.x      = clamp(target.x, ..., offside_line_if_attacking)          # attackers stay onside unless the role says "run the line"
```

Each step the player moves toward `target` at `v = v_max(pace, acceleration, energy)·Δt`; a player never teleports. **Roles change behaviour** in three ways: (1) offsets (an `inside_forward` drifts centrally in possession; a `fullback_overlap` pushes to x≈0.8 on the touchline; a `fullback_inverted` tucks to a pivot beside the DM), (2) freedom radius (how far he leaves the slot to receive or press), (3) action utility biases (§5.2). **Formations** change spatial coverage: the number of players in each horizontal band (a 3-5-2 loads the midfield band and exposes the flanks to a counter; a 5-3-2 with a low line concentrates ≥5 bodies at x<0.35). The openness and pressure calculations below read these positions, so shape differences appear as different pass-availability and chance-quality distributions.

### 4.2 Derived spatial quantities (all from current positions)

- **Pressure on carrier** `P ∈ [0,1]`: Σ over the 3 nearest opponents of `w(d)·intensity_i`, where `w(d)=max(0, 1 − d/R_press)`, `R_press = 3 m + 8 m·press_intensity`, `intensity_i` from the presser's `work_rate`·`aggression`·energy. Out-of-possession press triggers (`press_trigger`) switch the pressing intensity on only in the trigger situations (e.g. backpass, loss of ball), otherwise it is capped at the baseline.
- **Openness of teammate j** `O_j ∈ [0,1]`: based on distance to nearest opponent and whether the passing lane is blocked (point-to-segment distance to the 2 nearest defenders, sqrt only).
- **Defensive line x** and **offside line** (second-last defender), **space behind the line** (for through balls).
- **Zone control** per third (count of players, local numerical superiority) → used for momentum and chance creation.

## 5. Possession and the action-chain model

The match is a sequence of **moments**, each resolved as one on-ball action or one dead-ball restart. Every moment: (1) advance positions to `t`, (2) the carrier chooses an action, (3) it resolves, producing one or more events, (4) possession/ball state updates, (5) `t` advances by the action's duration.

### 5.1 State

`ball{pos, carrier_id|None, in_play}`, `possession{team, chain_id, chain_len, since_t}`, `phase`, per-player `{pos, energy/exhaustion, yellow, sent_off, injured, subbed_off, minutes, stats, day_form}`, per-team `{tactics, score, subs_used, windows_used, momentum, pressing_state}`, `clock{t, period, scheduled_end, added_time}`.

### 5.2 Choosing an action (decision model)

Candidates for carrier *c*:
- `pass` to up to 5 teammates (best 5 by option score), each with a *kind* (short, long, through, cross, cutback, switch, back);
- `dribble` in 3 directions (forward, wide, cut-in);
- `shoot` if within range (≤ ~35 m, within an angle that gives non-trivial xG);
- `clear` when pressed in the defensive third (`P` high, own third);
- `hold/recycle` (back-pass, keep ball) when risk is punished.

Utility of an option:

```
U = w_prog·Δthreat + w_keep·P(success) + w_shot·xG_bonus − w_risk·(1−P(success))·cost_of_loss(zone)
    + bias_role(kind) + bias_trait(kind) + bias_tactics(kind) + noise
```

- `Δthreat = threat(end) − threat(start)`, where `threat(x,y)` is a smooth analytic surface (a polynomial in attack-normalised x and centrality; calibrated so that a pass into the 6-yard-box region ≈ 0.10 and own-box ≈ 0.001).
- `w_prog`, `w_risk` come from `mentality`, `passing_directness`, `risk_taking`, game state (trailing → ↑ progression, leading → ↑ keeping), and the carrier's `flair`.
- `cost_of_loss(zone)` is higher in the defensive third (the penalty for a dumb pass is a conceded chance) — this is what makes defenders play it safe and a flair winger gamble.
- Selection is a **softmax** with temperature `τ = 0.35·(1.3 − decisions_eff/100)·(1 + 0.4·P)`: good decision-makers choose near the best option; stressed or poor ones scatter. Softmax is implemented by cumulative weights using `1/(1+…)`-style rational weights (no `exp`): weight = `max(ε, 1 + β·(U − U_max))^k` with integer `k` — monotone, cheap, exactly reproducible.

### 5.3 Resolving actions

`squash(z) = 0.5 + 0.5·z/√(1+z²)` is the universal bounded S-curve (∈ (0,1), exact with sqrt).

- **Pass success** `p = clamp( base_pass(kind, length) + 0.35·squash((skill − 55)/25) − 0.30·P_carrier − 0.20·(1−O_j) − wind/rain terms + C_team + home/crowd term, 0.02, 0.985)`. `skill` combines `short_passing/long_passing/crossing`, `first_touch` of the receiver, `vision` (for through balls), `weak_foot` if the foot is wrong. Failure splits into: intercepted (by a specific defender weighted by proximity, `anticipation`, `positioning`) → `interception`; blocked/deflected; overhit out of play (→ throw-in/goal kick/corner); or a loose ball (a contested "second ball" micro-resolution that chooses the winner by `strength`/`pace`/`anticipation`).
- **Dribble**: success vs the nearest defender: `dribbling, agility, acceleration, balance, flair` vs `tackling, anticipation, pace, positioning`; outcomes: beaten (progress + pressure drop), dispossessed (`tackle` event, defender wins), fouled (→ §6), or run out of play.
- **Tackle/duel** events occur on dribble contests and when the defending team presses the carrier on reception.
- **Shot**: `xg = squash-based f(distance, projected goal-mouth width, body part, assist type, pressure, defenders in lane)`. The goal-mouth projection uses `7.32·dx/d` (no trig). Finishing modifies it: `xg_eff = xg·(0.80 + 0.40·finishing_eff/100·…)` bounded; `composure` reduces the pressure penalty; `long_shots`/`heading` replace `finishing` for those shot kinds. Outcome roll: blocked (≈ defender density), off target, on target → keeper: `save_p = f(shot placement quality, shot_stopping_eff, agility, positioning/sweeping, shot power proxy)`; the remainder = goal. Woodwork ≈ 2% of on-frame shots. Saves resolve into held / parried to safety / parried for a rebound (a micro-chain: the nearest attacker/defender race) / corner.
- **Clearance** vs. pressure: long hoof with low accuracy; may go out (throw-in/corner) or find a teammate/opponent.
- **Offside**: on a forward pass, if the receiver is beyond the offside line the call is made with probability `0.88 + 0.10·ref.consistency` (else error: a wrongly-allowed goal-chance or wrongly-flagged run — both feed VAR drama at M10). `off_ball_movement` and the line's `positioning` determine how often the sim *attempts* that pass (utility penalty × timing luck).

### 5.4 Durations and tempo

`dt(action) = base[action]·tempo_scale·(1 + noise)`: short pass 1.6–2.6 s, long pass 3–4.5 s, dribble 2–4 s, shot 1.5–2.5 s. `tempo_scale` from `tempo`, mentality and momentum. Dead-ball intervals are drawn per restart (throw-in 6–14 s, goal-kick 12–22 s, free-kick 15–35 s, corner 18–30 s, goal celebration & restart 45–70 s, substitution 25–45 s, injury treatment 30–120 s by severity, card 20–40 s, review 50–150 s). A match yields ≈ 1,000–1,400 on-ball events; ball-in-play ratio is targeted at 58–64%.

### 5.5 Possession change, transitions, momentum

On turnover the winner enters `transition_att` for ~6–10 s (`on_win: counter` raises tempo and forward-bias; `hold_shape` forces recycling). The loser enters `transition_def` (`counter_press` for ~5 s of high press intensity at high energy cost; `regroup` drops into shape). **Momentum** per team `m ∈ [−1,1]` (home positive) updated from the last 10 minutes' weighted shots/xG/territory/possession with exponential-like decay implemented as a fixed-weight window (no `exp`); it feeds tempo and *very* mildly attacker composure (±1.5%), and is exposed in every event for the commentary layer.

## 6. Set pieces, fouls, discipline, referee

**Fouls.** A foul candidate arises from contested actions (tackle on a dribbler, aerial challenge, shielding, a late tackle after a pass). `p_foul = base_contact·(0.6 + 0.8·aggression_eff + 0.5·dirtiness − 0.5·tackling_eff/100)·tackling_style_factor·derby_factor`. The referee then **calls** it: `p_call = squash((severity − threshold_ref)/s_ref)` where `threshold_ref = 0.55 − 0.25·strictness + home_bias_term(team, crowd) + noise(1 − consistency)`. Uncalled contact continues play (plus advantage possibility via `advantage_tendency`). This yields differing foul counts across referees and the home-bias effect from marginal calls only.

**Cards.** Given a called foul with severity `s`: yellow if `s > thr_y(strictness, card_tendency)`, straight red if `s > thr_r` or if it denies an obvious goal-scoring opportunity (carrier through on goal, ≥ 0.4 xG lost), or second yellow. Dissent/time-wasting cards occur at low rates driven by `volatility`/`time_wasting`. A sent-off player's slot becomes empty; the AI manager's response (§11) fires immediately.

**Penalties.** A foul inside the box becomes a penalty with `penalty_propensity` weighting (ties to ref personality); conversion `p = 0.77 ± (penalty_taking, composure, big_match vs keeper one_on_ones, handling)`. 

**Throw-ins / goal kicks / corners.** Out-of-play restarts: possession to the right team; throw-in uses the nearest suitable fullback/winger (`long_throw` trait → box delivery); goal kick tactic (`build_up: short_gk` vs long); **corners**: taker by `set_piece_delivery`, routine from tactics; delivery quality vs. marker/aerial duel resolution: `attackers_in_box` with `heading, jumping_reach, strength, height, bravery, off_ball_movement` vs. defenders `marking, heading, positioning, jumping_reach` and keeper `aerial_command, communication`; results: cleared, headed shot (→ shot model, `assist_type=corner`), keeper claims, second ball, goal. **Free kicks**: direct shot if within ≈ 32 m and taker's `set_piece_delivery/long_shots` suffice (wall effect), else a cross or short pass.

**Advantage** and **added time** (§12) complete the flow.

## 7. Substitutions and tactical state

Rule set (from `MatchRules`): max 5 subs in max 3 windows + half-time. Substituted players never re-enter. Bench must hold ≥ 1 GK. Injury substitutions beyond the window limit are allowed only if the team has subs left (forced replacement can use any window). A team that has used its subs and suffers an injury plays short.

## 8. Home advantage — decomposed

Total target effect ≈ +0.25–0.30 goals/match and a home-win rate of ~45%. Each channel is small, bounded, and traceable:

| Channel | Mechanism | Fields |
|---------|-----------|--------|
| **Crowd lift** | `crowd = fill·atmosphere·proximity·passion·stadium.home_advantage.crowd_weight` (0..1, `fill = attendance/capacity`). Home mental effective attributes `+ 2.5%·crowd`; away composure/concentration `− 2.0%·crowd·(0.5 + 0.5·toxicity)`; scaled by each player's `big_match` and (away) `personality.resilience`. | `Stadium`, `Fanbase`, attendance |
| **Referee bias** | marginal-call tilt `home_bias·crowd·ref_pressure_weight` applied to `threshold_ref` for fouls/cards/penalties (it can even be negative = overcompensating referee). | `Referee.home_bias`, `Stadium.home_advantage.referee_pressure_weight` |
| **Familiarity** | home `M_ctx` on passing/touch of up to +1.0% from `pitch.quirks` & pitch dimension fit with the tactics (narrow pitch penalises width-heavy visitors). | `Pitch`, `familiarity_weight`, tactics |
| **Travel/altitude** | away fatigue accrual × `(1 + 0.04·travel_weight + altitude_factor)`. | `altitude_m`, `travel_weight` |
| **Psychological tempo** | Home momentum seed `+0.05` at kickoff; away teams in hostile environments are more prone to losing structure when conceding first (briefly higher `volatility` effect). | `toxicity`, personality |

Everything is multiplied by the global `home_advantage_scale` config constant, used by the calibration loop. Played on a neutral venue (`fill=0, scale 0`), the home-win rate collapses to ≈ the away win rate — a test.

## 9. Fatigue, fitness, injuries

**In-match exhaustion** `E_ex ∈ [0,1+]` per player: starts at `E0 = 0.6·fatigue + 0.4·(1 − fitness)` (carried-in tiredness plus lack of conditioning), then **monotonically increases** per Δt:

```
dE = Δt/5400 · drain_rate
drain_rate = base · (1.1 − 0.5·stamina_eff/100) · (1.05 − 0.25·natural_fitness/100)
           · role_load(duty, position) · press_load(press_intensity, press_role) · tempo_load
           · (1 + 0.5·heat) · (1 + 0.25·wet) · (1 + 0.5·work_rate_eff/100 − 0.25) · away_travel_factor
           · (1.15 if in an active sprint-heavy phase, else 1.0) · (1 + 0.1·extra for being 10 men / tracking back)
```

No recovery during play (only a small, explicit `halftime_recovery` applied inside the `halftime` handler, recorded in the event). This implements "fatigue only increases during play". GK drain ≈ 25% of an outfielder's.

**Injury hazard** per player per Δt: `h = h0 · (0.5 + proneness/60) · (1 + 1.5·E_ex²) · contact_exposure · pitch_factor(quality, wetness, frozen) · (1 + 0.3·bravery_eff/100) · 1/(1 + balance/150)`. Contact exposure is higher at event moments (tackles, aerial duels, sprints) — in practice the injury check runs **at contested events** (probability per contact) and at a low background rate for non-contact injuries. Severity distribution from `injury_types.yaml`: knock (play on, −performance for N minutes), minor (sub), moderate, severe; `expected_return_days = base·(1+proneness/100)·(1 − 0.3·medical/100)` (L). Appearance of an injury creates a stoppage and, for non-`knock` cases, a forced substitution decision.

## 10. Weather and pitch

| Input | Effect |
|-------|--------|
| `rain_mm_per_h`, `pitch_wetness` | Faster, skiddier ball: pass accuracy ↓ for long passes (−4% heavy), `first_touch` penalty (−3%), slips (dribble success ↓), shot pace ↑ (keeper difficulty ↑); injury hazard ↑ (×1.15 at wet); `pitch.drainage` mitigates. |
| `wind_speed`, `wind_direction` | Long ball/cross/corner distance and accuracy shift along the wind vector; switches ends at half-time (a real tactical asymmetry in period 1/2). |
| `temperature_c`, `humidity` | Heat (>26 °C, humid) multiplies fatigue drain (`heat` term) and lowers concentration late; cold (<3 °C) raises muscle-injury hazard (×1.1) and lowers first touch slightly. |
| `daylight`/`visibility` | R (fog affects long passing/commentary colour; shows in preamble). |
| `pitch.quality` | passing & dribbling reliability, bad-bounce chance, injury; interacts with `surface`. |

## 11. AI manager: tactical changes and substitutions

Each manager is an agent evaluating the match at **checkpoints**: every `review_interval = 300 s·(1.4 − 0.8·flexibility)` ± jitter from stream `mgr_<side>`, **plus triggers**: goal scored/conceded, red card, injury, half-time. The agent sees only **observable** state with noise (`tactical_knowledge`, assistant's `tactical_input` reduce the noise): score, minute, cards, a noisy estimate of xG-share and territory for the last 15 min, the opponent's apparent formation (mis-read with probability `0.25·(1 − tk)`), and per-player apparent tiredness (noise from `judging_ability`).

```
state := assess(match)  →  {game_state: leading|level|trailing, margin, minutes_left, men_difference,
                            momentum_trend, xg_share_15, fatigue_flags, yellow_risk_flags, injury_flags}
options := candidate_actions(state)    # incl. "do nothing" with a prior favouring stability
choice  := softmax_sample(utility(options, manager_profile), τ = f(tactical_knowledge))
```

**Candidate actions**
1. *Forced injury sub*: best bench player for the slot by `position_competence`, role fit; same-position preference unless chasing.
2. *Fatigue sub*: replace the most-exhausted player (or lowest effective-per-slot) with a fresh bench player when `minute ≥ sub_habits.earliest_minute`, within a preferred window, `fresh_legs_bias` weights it.
3. *Chase game* (trailing, minute ≥ 55; strength ∝ `chase_game_bias`, gap, minutes left): replace a DM/CB/FB with an attacker; raise mentality; raise line/press; if flexible enough and has a fallback formation with more forwards, change formation (cost: transient cohesion dip `−2%` for 8 minutes scaled by `formation_proficiency` and `adaptability`).
4. *Protect lead* (leading, minute ≥ 70; ∝ `protect_lead_bias`): replace a forward with a defender/anchor, drop line, `time_wasting ↑`, mentality ↓.
5. *Red card reshape* (own player sent off): drop an attacker for a defender/pivot; switch to a 4-4-1 / 5-3-1-like fallback; or (opponent sent off) push mentality up.
6. *Yellow-risk sub*: replace a booked player with high `dirtiness`/`aggression` between minutes 60 and 85 if `reacts_to_cards` high (managers pull a booked player late, not in the first half).
7. *Opponent threat response*: if the opponent winger/formation exploits a flank (xG-share by lane), shift roles/instructions on that side or swap a fullback.
8. *Half-time talk*: choose `style` by manager personality/`motivation` and the situation (praise/calm/fire-up/tactical); morale delta ∈ [−0.04, +0.06] on mental effective attributes for the second half, scaled by `man_management`/`motivation` and each player's `ego/resilience`. Recorded in the `halftime` event.

Constraints: window limits, cooldown (≥ 8 min between formation changes), max 2 formation changes, never lose the only GK, reds can't be replaced. Every change emits a structured `substitution`/`tactical_change` event with `reason`, so the commentary layer needs no inference. All decisions use only manager-stream RNG; swapping the manager AI does not change the play stream.

## 12. Stoppage time, momentum, match flow

**Added time** per half = `ceil(ref.added_time_generosity_factor · (Σ stoppage seconds of subs, injuries, goals/celebrations, reviews, cards, time-wasting) / 60 · 0.65)` clamped to [1, 8] (second half [2, 10]); announced via an `added_time` event at 45′/90′ with the figure. Play continues until the ball is next dead after the time elapses (the sim lets the current chain finish, ending at the next stoppage or after a max overrun).

## 13. Determinism and numerics (implementation notes)

- **`SimRng`** is a self-contained integer generator (xoshiro256** seeded through splitmix64, ADR 0005) because the architecture rules forbid importing `random` in `sim/`. It exposes only `u()` (uniform [0,1) from 53 random bits), `u_int(n)`, `choice_weighted`, `gauss()` (Irwin–Hall: `(Σ4 u − 2)·√3`), `bernoulli(p)`, and a `draws` counter. `fork(label)` derives a child seed via `blake2b(seed‖label)`; child streams are independent instances.
- Float outputs rounded at emit (`pos` 4 dp, probabilities 4 dp, seconds int). Events serialise through the model (`model_dump_json()`: field-declaration key order, shortest round-trip floats, no whitespace); `canonical_json()` (sorted keys, `ensure_ascii=False`, `separators=(",",":")`) is used for config hashes and golden files (ADR 0006).
- The final `match_summary` contains `log_digest = sha256(model_dump_json() lines of all prior events, newline-terminated)` (ADR 0006); the golden test pins digests for 5 seed/team pairs; CI runs on Windows and Linux.
- Everything is ordered: players iterated in slot order; dicts avoided in hot paths or iterated sorted.
- No `set` iteration; no `hash()`; no `id()`.

## 14. Balance targets (what the statistical tests assert)

**What "realistic" means here.** The default numbers are my recollection of typical long-run averages for elite men's top-flight football (about 2.6–2.8 goals per match; roughly 45% home wins / 25% draws / 30% away wins; ~11–13 shots per team with ~10% converting; ~80–85% pass completion; ~3.5–4 yellow cards and ~0.1 red cards per match; ~0.3 penalties per match; ~10 corners; ~22–25 fouls). They come from general knowledge, **not from a dataset I looked up** — treat them as reasonable starting points, not facts. The bands are deliberately a bit wide, and an 8-team league with one dominant club will naturally show slightly more lopsided results than a 20-team league.

**Everything is tunable.** Targets live in `data/static/balance_targets.yaml` (one entry per metric: `target`, `min`, `max`, `weight`, `tier`), grouped into named **profiles** (`realistic` — the default; `high_scoring`; `defensive_grind`; `chaos` — more upsets/cards/injuries for entertainment; `custom`). You choose the profile (`--profile`), edit any band, or add your own; the sim's behaviour is tuned by `SimConfig` knobs (§14.6). Nothing about "what a good league looks like" is hard-coded in tests — tests read the active profile. Phase 2 (M8) ships the harness that shows pass/fail per metric and fits the knobs to whichever profile you pick.

Measured over ≥ 1,200 seeded matches spanning all pairings of the generated league (both venues) and over an extra "stress" set with extreme strength gaps.

### 14.1 League-level aggregates (pooled)

| Metric | Target (band) | Notes |
|--------|---------------|-------|
| Goals per match (both teams) | **2.70 (2.45–2.95)** | |
| Home goals / away goals | ≈ 1.50 / 1.20 | home share 53–58% |
| Home win / draw / away win | **45% (41–49) / 25% (22–29) / 30% (26–34)** | |
| Scorelines | 0–0 ≈ 6–9%; total goals ≥ 5 ≈ 14% (10–18%); any team ≥ 5 goals ≈ 2.5% (1–4%) | A Poisson fit at a mean of 2.7 gives 13.7% for 5 or more; a published Premier League analysis at 2.88 puts 6 or more at 8.5% (M8 changed the original ≤ 7% / ≤ 2%) |
| Goal timing | 2nd-half goals 53–58%; last 15 min (incl. stoppage) 22–28% | fatigue effect |
| Shots per team | 12.5 (11–14) | |
| Shots on target / shot | 0.33–0.40 | |
| Goal conversion / shot | 9–12% | mean xG/shot ≈ 0.10 |
| Pass completion | 80% (75–86%) | |
| Possession share spread (σ across matches) | 6–10 pp | |
| Corners per match (both) | 10.0 (9–11.5) | |
| Offsides per match (both) | 3.8 (3.0–5.0) | |
| Fouls per match (both) | 22 (19–26) | |
| Yellow cards per match (both) | 3.6 (3.0–4.4) | |
| Red cards per match | 0.11 (0.07–0.16) | straight + second yellow |
| Penalties per match | 0.27 (0.20–0.35); conversion 74–80% | |
| In-match injuries per match (both, any severity incl. knocks) | 0.40 (0.25–0.60); of which forced substitutions ≈ 40% | |
| Substitutions per team | 4.2 (3.5–4.9); no sub before minute 45 except injuries | |
| Ball-in-play fraction | 58–64% | |
| Average added time (both halves) | 1.8 / 4.2 min (±1) | |

### 14.2 Strength and upsets

Let `rating_gap` = team strength difference on the 0–100 team-rating scale (effective-attribute composite of the XI, computed by `ratings.team_rating`). Pooling both venues symmetrically:

| Gap bin | Favourite wins | Draw | Underdog wins |
|---------|----------------|------|---------------|
| < 3 (even) | 35–42% | 24–30% | 33–40% |
| 3 – 8 | 44–53% | 24–30% | 20–30% |
| 8 – 15 | 55–66% | 19–27% | 11–21% |
| > 15 | 66–80% | 14–23% | 5–14% |

Also: favourite win rate is strictly increasing in gap bin; expected goal difference is ≈ linear in gap (slope assertion); home favourite > away favourite at the same gap by 5–12 pp.

### 14.3 Season-level (via `league` runs, ≥ 200 seasons overnight; ≥ 20 seasons in CI "slow" tier)

- Spearman(rating rank, final rank) 0.70–0.92.
- Highest-rated team wins the title 35–55% of seasons; lowest-rated ≤ 3%; points-per-game of champion 1.9–2.4; of last place 0.6–1.0.
- Unrelated invariants: points total = 3·W + D identity, goals for = goals against league-wide.

### 14.4 Behavioural sanity ("metamorphic") tests

Home advantage ↓ at neutral/empty stadium; +5 on all attributes of a team raises its win rate; red card to team X lowers X's expected points; trailing teams raise shot share after minute 60; exhausted players concede more late; heavy rain lowers pass accuracy and raises error rate; strict referee yields more fouls/cards than a lenient one; a 5-3-2 low block concedes fewer shots but creates fewer too, vs. a 4-3-3 high press.

### 14.5 Calibration procedure

`uv run balance` (package `src/footystreams/balance/`, pure Python: the objective costs seconds per call, so numpy buys nothing; not part of the sim, and `tools/` may not import project code, hence the own layer in the architecture rules) plays N matches over every ordered pairing of a world's clubs (default: `data/worlds/default`, 56 pairings; each replicate draws its own weather, referee and crowd; match seed = `base_seed + i`) across a process pool and prints each metric with value, 95% interval (batch means), target, band and PASS/LOW/HIGH/n-a. The result is a pure function of the scenarios and the config, whatever the worker count. `balance fit` runs a derivative-free Nelder-Mead search over chosen knobs, as multipliers of their defaults inside bounds, to minimise the weighted squared miss (in band half-widths, capped per metric) against the profile, then re-measures the winner on fresh seeds and writes a **candidate** partial config; it never overwrites a file and never touches a shipped default. The tuned values are committed as the `SimConfig` defaults. Once the defaults are calibrated, a 200-match test (bands widened 2x) and a 1,200-match test (real bands) under `tests/statistical/` guard against drift (PR tier and nightly / milestone close); they land with the calibration.

### 14.6 How you tune it

1. **Targets:** edit `data/static/balance_targets.yaml` or pick a profile (`realistic`, `high_scoring`, `defensive_grind`, `chaos`; a profile `extends` another and lists only what differs); `uv run balance --profile realistic --matches 1200` prints every metric. Nothing else hard-codes a target.
2. **Knobs:** every float of `SimConfig` is a knob addressed by its dotted path (`shot.xg_cap`). Override with `--config my.yaml` (partial files merge over the defaults; the `config_hash` changes, so matches record which config produced them) or `--set group.knob=value`; unknown or out-of-range values are usage errors.
3. **Sensitivity report:** `uv run balance sensitivity --group shot,passing` nudges each knob by -20% and +20% (`--relative`) on the same scenarios and prints a knob x metric matrix in band half-widths, with the run's own noise in the second row and `*` on effects above it, then names the three strongest knobs per metric. `--knobs a,b` picks knobs by name; `--sides up` nudges only upward (half the cost, falling back to down for a knob already at its maximum). `--state FILE` saves one JSON line per finished knob and resumes from it (refusing a file made with different matches, seed, nudge, metrics, config or `SIM_VERSION`); `--report FILE` also writes the table.
4. **Auto-fit:** `uv run balance fit --group shot --out candidate.yaml` (see 14.5); review the candidate, apply it with `--config`, re-run `balance`, then commit the numbers as defaults together with the golden update.
5. **Per-team/league levers** (no code): world-generator strength spread, referee pool, stadium home-advantage scalars, weather climate bands.

Not measured: ball-in-play fraction (the log has no out-of-play durations) and the expected-goal-difference-versus-gap slope; the metamorphic list is covered by `tests/statistical/test_m6_metamorphic.py`, `test_m5_rules.py` and `test_strength.py`, except red-card points and the 5-3-2 low block versus 4-3-3 press comparison.

## 15. Performance budget
(*Component structure and the path to richer tactics — gegenpressing, triangles, pass maps, frame data — is in `08-roadmap.md`: the sim is built from Protocol-typed components selected by `SimConfig.model_profile`, so v2 models slot in without changing the event contract.*)


Target **≤ 150 ms mean per match single-core including event validation** (p95 ≤ 220 ms, p99 ≤ 300 ms; the full budget table and the optimisation rules are in 11 §6; the tests that enforce them in 10 §6). ≈ 1,200 moments, 22 position updates every 4 s ⇒ ≈ 1,350 position steps, 5–8 candidate evaluations per moment, so 1,200 matches ≈ 3 min single-process, < 50 s with 4 workers; the 4 matches of a matchday run in parallel inside the league layer. Tactics: lazy position updates (only the 10 nearest players to the ball use fine resolution), `__slots__`/dataclass for mutable internal state (Pydantic only at the boundary). **Every emitted event is constructed through its Pydantic model (full validation, ≈ 10 µs each, ≈ 15 ms/match)** — validation is never skipped; if profiling shows it dominates, the fallback is `model_construct` in production plus full `model_validate` of every event in the test suite and in `--strict` CLI mode, and that change would be flagged to you first. Precomputed role/formation tables as tuples.

## 16. Implementation notes (Track A, kept current per milestone)

What the code does where it differs from, or fills in, the text above. Deviations are also listed in `docs/milestones/M4.md` onward.

**M4 (sim kernel).**
- *Contracts.* The frozen M1 event models are slimmer than section 3 of `03-events.md` (no `kind`/`outcome` enums on every event, `MatchClock` is `{period, minute, second, stoppage}`, `chain_id` is a string, no preamble or `frame` payload). The sim emits exactly the M1 shapes; fields the design lists but M1 lacks are not invented. `events/clock.py` converts playing seconds to the displayed clock and back.
- *Setup.* `MatchSetup` carries `referee_id` only; the referee model (M5) takes an optional `Referee` argument to `simulate_match`. Formations come from `StaticTables` (eight built-ins in `sim/formations.py` until the YAML loaders of M2 exist); `MatchSetup` has no `rules` field, so the substitution limits are `SimConfig` knobs (M6).
- *Moment loop.* Positions refresh once 2 s of match time have passed (`PositionConfig.step_s`; 4 s before SIM 0.6.0), not after every action. A moment is: press tackle attempt, else carrier decision (4 candidate receivers plus one safe outlet, a dribble, a shot in range, a clearance under pressure) and its resolver. One random draw per decision, one per resolution step, all from the `play` stream.
- *Calibration.* xG geometry is `cap * u^3 / (u^3 + half)` with `cap = 0.40` (section 5.3 quotes the unscaled anchors); pass, dribble and tackle skill swings are damped (0.12, 0.12, 0.10) so a 5-point team gap is roughly even and a 15-point gap wins about 75%. Defaults give about 3.0 goals, 14 shots a side, 43% on target, 85% pass completion. These are rough: the balance harness (M8) fits them.
- *Digest.* `log_digest` is sha256 over the NDJSON of `model_dump_json()` lines (field-declaration key order), not sorted-key canonical JSON: a pure function of the validated model, about 7x faster (ADR 0006, pending owner sign-off).
- *Restarts.* A goal's celebration advances the match clock but not the position update: `place_for_kickoff` is the walk back, and the first action after the restart starts from the kick-off formation.
- *RNG.* Own xoshiro256** generator (ADR 0005) because `random` is banned in `sim/`.
- *Not yet.* Out-of-play restarts, fouls, offsides, cards (M5); fatigue, injuries, substitutions, weather, home advantage (M6); momentum, tags, ratings, frames (M7). `model_profile` is recorded in the config but there is a single implementation; the Protocol seams are introduced when a second implementation exists.

**M5 (dead balls, discipline, referee).**
- *Referee.* `simulate_match` / `run_match` take an optional `Referee` (the setup holds only `referee_id`); without one a neutral referee officiates. A contact is called with `squash((severity - threshold) / 0.12)`; the threshold falls with strictness, jitters with inconsistency and is tilted by `home_bias x crowd` (crowd = attendance / 40,000 until stadium capacity is wired in M6).
- *Event shapes (M1 contracts).* `foul` has only a severity label; advantage is therefore encoded by the absence of a restart after the `foul` (a card may still follow). `card.colour` is `yellow | red | second_yellow` (a second booking is one `second_yellow` event, counted as a yellow and a red in the summary). Offside is `pass(outcome=complete)` followed by `offside` and an indirect `free_kick`; a missed flag simply lets play go on. A scored penalty is `penalty(outcome=goal)` then `goal` (no separate `shot`); a saved one is followed by a `save` caused by the penalty. `ctx.men_*` is "after" the event, as the score is (a card's context already shows the dismissal).
- *Rules the sim defines.* A side is never reduced below 7 players: past that point the referee shows no further cards (`DisciplineConfig.min_players`). A sent-off goalkeeper is replaced by the outfielder with the best handling; M6's bench goalkeeper takes precedence once substitutions exist. Penalties exist only inside the area and the referee is deliberately reluctant (`box_leniency`).
- *Restarts.* A ball leaves the pitch from an overhit pass, a deflected cross, a shot off target (goal kick), a blocked or parried shot (corner), a clearance (touch or, near the own goal, behind), or a heavy touch; the classification (touch line: throw-in; goal line: goal kick or corner by last touch) is in `actions/out_of_play.py`. Corners and crossed free kicks share one aerial duel: the attackers sent into the box (tactics `corner_attackers`) against the five best defenders, the taker's delivery lifting the attackers' share; the branches are keeper claim, header shot (the normal shot model) and clearance with a second-ball contest.
- *Offside.* Attackers stand just short of the second-last defender (sharper movers closer); passes to a receiver beyond line and ball are flagged with `0.88 + 0.10 x consistency`; receivers level with the line may be judged offside for a mistimed run (`mistime_base`), a stand-in for run-timing detail the position model does not have. M8: the run can only be mistimed on a through ball, long ball or cross (a short pass to a feet-receiver is not a run in behind), and after every position step `update_positions` pulls back an attacker the line has dropped behind (the ceiling alone limits only the target, and left half of all offsides: 14.7 a match became 5.1).
- *Added time.* Goal celebrations and card delays accumulate as stoppage; `ceil(generosity x minutes x 0.65)` is announced at the end of each period (clamped 1-8 and 2-10) and played. Substitutions and injuries will add to it in M6.
- *Streams.* `discipline`: contact, severity, call, advantage, DOGSO, offside flag. `setpiece`: restart delays, corner and free-kick branches, penalties, deflections. The `play` stream still draws every on-ball decision and the shot outcome of corner headers and free kicks.
- *Denied goal-scoring chance (M8).* `denies_opportunity` needs the fouled man past `dogso_min_frame_x` with at most the keeper ahead and an unpressured xG of at least `dogso_min_xg` (0.15) from where he stood: the stage 1 attacking volume had made 'through on goal' so common that reds ran at 1.4 a match (0.31 after).
- *Calibration stage 2: tactics leverage (M8).* Found by controlled experiment, not by fitting: with identical tactics the strongest club took 19.5 shots to the weakest's 6.4; with the seeded tactics the order inverted. Mentality scales the progress weight, line height and press move territory and pressure, and none carries a cost (a high line does not concede balls over the top; a press costs only a little stamina), so a high-press attacking side beat better teams and a patient possession side took 3 shots a match. `mentality_swing`, `directness_bias`, `line_range` and `pressure.radius_range_m` are a tenth of their stage 1 values (club rating vs points, Spearman: 0.21 at stage 1 leverage, 0.88 at a tenth, 0.98 at none). Follow-up: give style choices their costs (space behind a high line, press fatigue) and raise the leverage again; until then tactics are a small nudge. Result on 1,200 fresh matches: 28 of 43 metrics pass, loss 4.2.
- *Calibration stage 3: discipline and home advantage (M8).* Set by direct scans, because the fit could not move them: the yellow response is steep (`yellow_base` 0.70 gives 2.2 a match, 0.665 gives 3.4, 0.5 gives 10, and the booked players' extra care lowers fouls as it rises), second yellows fall with `second_booking_margin`, and `home_advantage.crowd_lift` 0.25 puts home goals, home goal share and home wins in band. Known gaps after M8: the goal timeline (second-half share 45%, last-quarter share 16%, against 55% and 25%: fatigue has no effect on it, so a fix is a design change to late-game dynamics), possession spread (5.4 against 8), corners (8.8 against 10) and the substitution rule (one change per stoppage).
- *Calibration stage 1 (M8, SIM 0.5.0).* The M7-era defaults played about 4.0 goals, 21 shots a side, 15 corners and 15 offsides a match. A damped Gauss-Newton fit (Jacobian from the all-knob and large-step sensitivity sweeps, residuals from real runs) moved `shot.min_xg` (0.02 to 0.06: a threshold, so the 20% sweep could not see it), `dribble.base`, `dribble.distance_m`, `decision.progress_scale`, `decision.shot_scale`, `decision.clear_pressure`, `passing.base_back` and `offside.mistime_base`. On 1,200 fresh matches: goals 2.70, shots 13.3 a side, corners 10.1, goals per shot 10.2%, pass completion 76.5%, scoreless 7.5%. Open after stage 1: discipline (reds 0.9 a match), substitutions (3.0 a side), the second-half and late-goal shares, and strength (the favourite barely outscores the underdog: the underdog is given more chances reached by short passes; see the M8 report).
- *Calibration (rough, M8 fits).* 100 demo matches: goals 2.9, shots 14.9 a side, fouls 25, yellows 3.6, penalties about 0.3, corners 10, offsides 3.4, throw-ins 17, goal kicks 12.

**M6 (fatigue, injuries, weather, home advantage, AI manager).**
- *Fatigue.* Exhaustion is per player, rises with a drain set by stamina, fitness, work rate, line, pressing, tempo, heat, wet pitch, altitude and travel, never falls inside a half and recovers a little at half-time (`FatigueConfig`). Skills are rebuilt from their pre-fatigue base only when exhaustion crosses a 0.05 step, so the hot path stays cheap. Events carry no fitness data, so the "never decreases" invariant (M09) is an engine-level test, not a `verify` check.
- *Weather and pitch.* `Conditions` is computed once per match from the setup's weather and the home stadium (`weather.py`): long-ball penalty (wet, wind, poor pitch), first-touch and dribbling multipliers, an injury multiplier, and heat and wetness feeding fatigue.
- *Home advantage.* The crowd channel only: `crowd = fill x mean(atmosphere, proximity, passion) x 2 x crowd weight` (a mean, not the design's product, which gave a vanishing effect for ordinary grounds), lifting the home side's mental attributes (scaled by `big_match`) and denting the away side's composure. `SimConfig.home_advantage_scale` is the lever; 0 is a neutral venue. The referee's home tilt (M5) is the second channel.
- *Injuries.* The `injury` stream only. A called foul and a clean won tackle roll against `foul_contact` / `tackle_contact`, and a low background rate (`non_contact_per_match`) strains a random player in open play, all scaled by a per-player hazard (proneness, exhaustion squared, bravery, balance, wet/cold/poor pitch). Severity comes from a built-in type table (`injury_types.py`, a stand-in for the design's `injury_types.yaml`); only the apparent severity and `can_continue` are on the event, the true diagnosis is kept in `MatchState.injury_log` for the M7 summary. A player who cannot continue is replaced in a *forced* change (outside the window limit) or, with no change available, the side plays short; a side at `min_players` keeps the hurt player on. A foul injury is emitted between the foul and its card.
- *Substitutions.* `subs.py`: at most `max_subs`, in at most `max_windows` stoppages (changes closer than `window_gap_s` share one; default 5 because the AI makes one change per stoppage, where the real rule is three windows with several changes in each, a follow-up), half-time free, forced injury changes exempt from windows, the bench goalkeeper only for a goalkeeper. The newcomer is built on the leaver's slot with the leaver's role and `Duty.SUPPORT`.
- *AI manager.* One agent per side on the `mgr_home` / `mgr_away` streams (`manager_assess.py`, `manager_plans.py`, `manager_ai.py`). Checkpoints every `300 s x (1.4 - 0.8 x flexibility)` with jitter, plus after goals and dismissals and at half-time; a review reads a noisy assessment (exhaustion misread more by managers with little tactical knowledge), weighs candidate plans (fresh legs, chase the game, protect the lead, react to a dismissal, replace a booked aggressive player) against a do-nothing prior, draws one, and carries it out at the next stoppage. Mentality moves along the ladder (cooldown `shift_cooldown_s`); a `tactical_change` event records it. A manager who never acts leaves the log byte-identical. Not implemented: formation changes, opponent-threat response, the half-time talk's morale effect.
- *Added time.* Substitutions and injuries now add stoppage seconds, so second-half added time is closer to the design.
- *Living movement (SIM 0.6.0).* A player is no longer drawn to a static slot. `sim/movement.py` adds three things to the slot target: a slow loop round it (`wander_m`, a smooth triangle wave of the clock and the slot, wider for sharp off-ball movers while their side has the ball; arithmetic only, no `sin`/`cos`, no random draw), pressing (the nearest `press_count x (0.5 + press intensity)` outfield players of the side without the ball close to `press_gap_m` goal-side of the carrier at `press_speed_bonus` x pace) and marking (each other defender or midfielder takes the nearest unmarked man within `marking_range_m` of his slot and blends toward a spot `marking_goalside_m` goal-side of him by `marking_weight`). Team-mates keep `spacing_m` from each other and `carrier_space_m` from the man on the ball (`spread_out`), only players within `press_range_m` press, and a goalkeeper with the ball is shown the way by one man who stops at the edge of the box. Targets stay `edge_margin` off the touchlines (before, wide players clamped onto the line and stood over it). In the final third a pass that gains no threat, or that returns the ball to the man it came from, loses `box_recycle_penalty` / `ping_pong_penalty` of utility so attackers do not shuffle the ball sideways. Frames move the ball and the player who gets it at `BALL_SPEED_MPS` and hold through a long moment (a throw-in delay no longer shows a crawling ball). Realism probes on a 90-minute SEI v BUK: outfield players standing still in a frame 62% to 22%; carrier with no defender within 8 m 22% to 8%; mean outfield speed 0.69 to 1.3 m/s.
- *Positioning order.* `update_positions` plans both teams' moves from the same positions and then applies them. Before this, the away side planned from the home side's already-moved positions (offside line, nearest players), a measurable away edge (about 0.25 goals a match) with home advantage off.
- *Calibration (rough, M8 fits).* 100 demo matches: injuries about 0.44 a match (design 0.25-0.60), 3.5 changes a match (the factory bench holds two outfielders and a goalkeeper a side, which caps it), 2.6 tactical changes.

**M7 (summary, ratings, context, frames).**
- *Where the code lives.* Everything derivable from the log is in `events/derive/` (pure; sim, `verify` and `analytics` all import it): `context.py` (the causal tracker), `tally.py` (counts), `presence.py` (minutes and departures), `maps.py` (pass matrix, zone flow, shot map, timelines, key moments), `ratings.py`, `hooks.py`, `threat.py` (the xT surface and the 12 x 8 grid, shared with the decision model) and `summary.py` (assembly). A summary can therefore never disagree with its log: `verify` M14 rebuilds it from the events and compares field by field. Two things the log cannot carry travel beside it in `SummaryInputs`: the true injury diagnoses (`MatchState.injury_log`) and each player's exhaustion at the end.
- *Context.* `ContextTracker` is a future-blind fold: momentum is the squashed home-minus-away balance of decaying credits (shots by xG, corners, penalties, threat gained by completed passes, small credits for dribbles and won tackles; linear fade over 180 s), intensity a squash of weighted events in the last five minutes, significance the old per-type rule plus boosts for the situation (late game, equaliser, go-ahead goal, ...). Tags are those of section 2.4 of `03-events.md` that the log supports; the ones needing outside facts (`high_stakes`, `former_club`, `milestone`, `rivalry_flashpoint`, `captain_involved`, `first_touch_of_sub`, `against_run_of_play`, `pressure_period`, `time_wasting`, `goal_disallowed_check`, `near_miss`) are not emitted. The momentum of an event does not include the event itself (causal), and replaying any prefix of a log reproduces the same context. The sim only computes it as it emits; nothing in play reads it.
- *Enrichment.* With `SimConfig.context.enabled` passes carry `end_pos`, `progressive` (a quarter of the pitch toward goal) and `xt_gain`, dribbles their `end_pos` and shots `big_chance` (xG at or above 0.3). Key passes are derived from `shot.assist_id`, so `pass.key_passes` stays False as the design says.
- *Summary.* Rows exist for everyone who played, with real minutes (substitutions, dismissals and unreplaced injuries end a spell). The position of a row is the player's best-competence position, not the slot he filled. Goals conceded are credited to the keeper in goal (a stand-in after a goalkeeper's dismissal is not credited). Ratings follow the weights of `03-events.md` section 5 where the log allows (no "errors leading to a goal" or psxg); the player of the match is the best rating, ties by goal involvement. Hooks implemented: late winner, comeback, hat-trick, red-card turning point, goalkeeper heroics, dominant but unrewarded, derby result; those needing league context (upset, debut goal, unbeaten run) wait for M9.
- *Frames.* Opt-in (`emit_frames`, `frame_interval_s`). A frame is the linear interpolation between the player positions at the previous engine step and the current one; they use no random draws and read the state only. Frames take sequence numbers, so a log with frames differs from one without in `seq`/`id`; the non-frame events renumbered are identical (tested, with context on too). The digest covers the whole log, frames included. The summary and the rules of play (`verify` M06-M08, M11, M12) ignore frames. Not implemented: `shape` metrics and `phase` on frames.
- *Cost.* Context and enrichment add about 70 ms a match on top of about 430 ms (the annotate fold ~50 ms, enrichment ~25 ms); the M8 performance pass should merge the two copies the tracker makes per event into one.
