# 01 — Entities and Schemas

Status: **PROPOSED (Phase 1)** — nothing here is implemented yet.
Package: `footystreams` (src layout). All models are Pydantic v2, `frozen=True` where they are snapshots, `extra="forbid"` everywhere.

## 0. Conventions

### 0.1 Usage legend (the "used now vs reserved" flag)

Every field in every table below carries one of these tags:

| Tag | Meaning |
|-----|---------|
| **S** | Read by the **match simulation** (M4–M8). Changing it changes match output. |
| **L** | Read/written by the **league/persistence layer** (M9): scheduling, standings, post-match updates, finances, attendance. Does not affect an in-flight match. |
| **R** | **Reserved.** Present in the schema, validated, seeded with plausible values, stored, exported to JSON Schema — but nothing consumes it yet. These exist so the LLM/TTS/renderer layers and later sim phases (transfers, development) need no schema migration. |
| **S+L** | Both. |

A test (`test_field_usage_registry`) keeps this honest: each model declares `__usage__ = {"field": "S"|"L"|"R"}` and the test fails if a field is untagged. Phase 2 will also report the S/L/R counts per model so dead-field growth is visible.

### 0.2 Primitive types (`footystreams/domain/types.py`)

| Alias | Definition | Notes |
|-------|-----------|-------|
| `Id` | `str`, pattern `^[a-z]{3}_[0-9a-z]{4,12}$` | Prefix by kind: `plr_`, `mgr_`, `clb_`, `stf_`, `ref_`, `med_`, `cmp_`, `ssn_`, `fix_`, `mch_`, `mem_`, `rel_`, `nat_`, `cty_`, `std_`, `prp_`. Typed `NewType`s per kind (`PlayerId`, `ClubId`, …) so mypy catches mix-ups. Generated deterministically from the world seed + a per-kind counter (base36). |
| `Attribute` | `int` 1–100 | **One skill of one person** (finishing, vision, pace…). 50 ≈ league-average starter *at that skill*; 70+ strong; 85+ elite; < 30 liability. Each player has ~50 independent `Attribute`s — that is where "good at different things" lives. |
| `Competence` | `int` 0–100 | **Suitability** for a position/role/formation (0 = cannot play it). ≥ 90 natural, 70–89 accomplished, 40–69 awkward. Not a skill; it scales skills. |
| `Reputation` | `int` 0–100 | **Standing in the world** (player, manager, referee, club). Moves slowly; never read as ability. |
| `Disposition` | `int` 0–100 | **Personality leaning** (ambition, humour, patience…). 50 neutral; neither good nor bad. |
| `Level` | `int` 1–100 | **Quality of a resource** (facility, academy, staff member overall). |
| `AbilityScore` | `int` 1–100 | **Derived summary** of a player (current/potential ability). Never the source of truth — see §1.9. |
| `Unit` | `float` 0.0–1.0 | Sliders, probabilities, fractions. Rounded to 4 dp on validation. |
| `Signed` | `float` −1.0–1.0 | Valence, bias, momentum. |
| `Money` | `int` | Whole units of the fictional currency **crown (Cr)**. Never float. Wages are per **week**. |
| `GameDate` | `datetime.date` | In-world calendar only. No wall-clock time anywhere in domain/sim. |
| `Pos` | `{x: Unit, y: Unit}` | Pitch coordinates, see §0.3. |
| `EntityRef` | `{kind: EntityKind, id: Id}` | Polymorphic pointer used by relationships, memories, proposals. |

**Why separate types instead of one shared `Rating`** (revision 4): an attribute, a competence, a reputation and a personality leaning all happen to be 0–100, but they mean different things, are generated from different distributions, move at different speeds and feed different parts of the sim. Distinct `NewType`s make mixing them a *type error* (mypy), keep each one's anchors/bands documented in one place, and let any of them change range or resolution later without touching the others. All are validated 0/1–100 integers on the same scale for simplicity. 1–100 (rather than 1–20) gives smoother gradients and lets seed generation hit target team strengths precisely.

### 0.3 Pitch coordinates

`x` runs along the length (0 = left goal line, 1 = right goal line), `y` across the width (0 = top touchline, 1 = bottom touchline), **absolute and fixed per match** so a renderer needs no flipping. The home team attacks toward `x=1` in period 1 and toward `x=0` in period 2. Internally the sim works in *attack-normalised* coordinates (own goal = 0, opposition goal = 1) and converts at emit time. Real pitch size (`length_m`, `width_m` from the stadium) is used for distance maths.

### 0.4 Shared person base

`Person` is a mixin used by Player, Manager, StaffMember, Referee, MediaPersonality:

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `id` | `Id` | S+L | |
| `first_name`, `last_name` | `str` (1–40) | R | |
| `known_as` | `str` | L | Display/short name used in logs and the CLI ("Okonvar", "Tomás Brae"). Unique within a world. |
| `pronunciation` | `Pronunciation{respelling: str, ipa: str\|None, stress_syllable: int}` | R | Produced for free by the name generator (it knows syllables). Gives the future TTS layer a pronunciation hint so invented names are not mangled. |
| `gender` | `Literal["male","female","nonbinary"]` | R | Needed for voice selection and consistent LLM prose. League is men's by default; media/referee/staff pools are mixed. |
| `pronouns` | `Literal["he/him","she/her","they/them"]` | R | LLM prose consistency. |
| `date_of_birth` | `GameDate` | S+L | Age is **derived** (`age_on(date)`), never stored — avoids drift. |
| `nationality` | `NationId` | R | Fictional nations. Name pools and flavour. |
| `second_nationality` | `NationId \| None` | R | |
| `birthplace` | `{city: str, nation: NationId}` | R | Commentary colour; hometown-club storylines. |
| `appearance` | `Appearance{skin_tone: 1–8, hair_style: str, hair_colour: str, facial_hair: str, build: str}` | R | Pixel-renderer input. Cheap now, painful to retrofit. |
| `personality` | `Personality` (§1.3) | S (players: lightly) / R | |
| `reputation` | `Reputation` | S+L | |

## 1. Player

`Player = Person + …` One row per player; the heavy sub-objects are nested models so JSON Schema stays readable.

### 1.1 Physical/identity

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `height_cm` | int 155–205 | S | Aerial duels, shielding. |
| `weight_kg` | int 55–105 | S | Strength/pace interplay; plausibility-checked against height (BMI 18–27). |
| `preferred_foot` | `left\|right\|both` | S | Which side a winger cuts in on; set-piece curl. |
| `weak_foot` | `Attribute` | S | Competence with the other foot; scales pass/shot quality when the sim picks the "wrong" foot (inverted winger on his strong side, defender under pressure). |
| `squad_number` | int 1–99 \| None | L | Unique per club (enforced at squad level, not here). |

### 1.2 Positions and roles (not a single position)

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `position_competence` | `dict[Position, Competence]` | S | **How good the player is when deployed in each position**, 0/absent = cannot play there. ≥90 = natural, 70–89 accomplished, 40–69 awkward. Effective attributes are scaled by competence (§02 §3). `Position` ∈ `GK, RB, LB, CB, RWB, LWB, DM, CM, AM, RM, LM, RW, LW, SS, ST`. |
| `primary_position` | `Position` | L | Derived cache of `argmax` competence. Used for squad-balance checks and the CLI. |
| `role_familiarity` | `dict[RoleId, Competence]` | S | Per role-and-duty familiarity (`RoleId` values come from `data/static/roles.yaml`, §02 §2). Scales role-specific behaviour bonuses. Absent ⇒ default 35. |
| `preferred_roles` | `list[RoleAssignment]` (≤4) | S | Used by the AI manager to auto-assign roles when building lineups. `RoleAssignment = {role_id, duty: defend\|support\|attack}`. |
| `traits` | `list[TraitId]` (≤6) | S/R | "Preferred moves"/player traits from the trait registry (`data/static/traits.yaml`). Each trait defines a hook into the action-utility function (e.g. `shoots_from_distance` ↑ long-shot utility; `cuts_inside_from_left` biases dribble direction; `dives_into_tackles` ↑ tackle attempt rate and foul rate; `long_throws`; `penalty_specialist`). The registry marks each trait S or R individually; the first release implements ~14 of ~30. |

### 1.3 Personality (shared with Manager)

`Personality` — every numeric field a `Disposition`, all **R** except where noted:

| Field | Meaning / future use |
|-------|----------------------|
| `ambition` | Wants bigger club/trophies. Drives transfer unrest, interview tone. |
| `loyalty` | Stays through bad times; resists leaving; strongest memory-weight for club events. |
| `professionalism` | Training/discipline consistency; fed to `consistency` of form drift (**L**: slows form decay). |
| `volatility` | Temper; reaction to being subbed/dropped/fouled. (**S**: tiny modifier on dissent/retaliation foul chance.) |
| `sportsmanship` | Fair-play attitude; feeds `dirtiness` priors and interview graciousness. |
| `ego` | Reacts badly to being dropped or out-performed; celebrations. |
| `sociability` | Forms friendships; dressing-room influence. |
| `humor` | Banter and press-conference tone. |
| `media_openness` | Candour in interviews. |
| `resilience` | Bounce-back after errors/defeats (**L**: scales morale recovery rate). |
| `archetype_tags` | `list[str]` derived deterministically (e.g. `"quiet_leader"`, `"hothead"`, `"joker"`, `"mercenary"`, `"one_club_man"`) for compact LLM prompting. |
| `interview_style` | `guarded\|candid\|bland\|combative\|humble\|cocky\|philosophical\|jokey` |

### 1.4 Attributes (1–100 each)

Four explicit nested models (explicit fields, not dicts, for typed access and readable JSON Schema). Outfield players carry low (5–20) goalkeeping values; goalkeepers carry low technical values except passing.

**`TechnicalAttrs`** (13): `finishing` (S: shot conversion/placement), `long_shots` (S: shots >20 m), `heading` (S: aerial duels, headed shots), `first_touch` (S: reception under pressure), `dribbling` (S: take-on success), `short_passing` (S), `long_passing` (S), `crossing` (S), `tackling` (S: tackle success, foul risk), `marking` (S: duel positioning, set-piece marking), `set_piece_delivery` (S: corner/FK quality), `penalty_taking` (S), `ball_shielding` (S: hold-up play, riding challenges).

**`MentalAttrs`** (14): `vision` (S: receiver-option range, through-ball detection), `decisions` (S: softmax temperature of action choice), `composure` (S: finishing under pressure, penalties), `anticipation` (S: interceptions, reading through balls), `positioning` (S: defensive shape discipline, offside timing), `off_ball_movement` (S: openness of receiver, evading offside), `work_rate` (S: pressing/recovery runs, fatigue drain), `aggression` (S: tackle attempts and fouls), `bravery` (S: contested headers, shot-blocking, injury exposure), `concentration` (S: late-game lapses), `determination` (S: fatigue resistance, comeback boost), `teamwork` (S: pass-network synergy, shape), `flair` (S: low-probability high-reward actions), `leadership` (S+L: team composure when captain, morale spread).

**`PhysicalAttrs`** (8): `pace` (S), `acceleration` (S), `stamina` (S: fatigue curve), `strength` (S: duels, shielding), `agility` (S: dribbling, saves), `balance` (S: injury avoidance in duels, shielding), `jumping_reach` (S: aerial), `natural_fitness` (S+L: recovery rate between matches, late-career decline).

**`GoalkeepingAttrs`** (7): `handling` (S: hold vs parry), `shot_stopping` (S), `aerial_command` (S: claims crosses/corners), `distribution` (S: goal-kick/pass accuracy), `one_on_ones` (S), `sweeping` (S: claims through balls, high line viability), `communication` (S: defensive organisation bonus).

**`HiddenAttrs`** (8; never shown to the commentary layer except through behaviour):

| Field | Use | Meaning |
|-------|-----|---------|
| `consistency` | S | σ of the per-match "day form" roll (§02 §3). High = reliably himself. |
| `injury_proneness` | S+L | Multiplier on injury hazard and recovery time. |
| `big_match` | S | Scales effective composure/concentration when `match.importance`, derby flag or crowd intensity is high. |
| `dirtiness` | S | Foul severity and off-the-ball incident propensity. |
| `versatility` | L | How quickly position competence in new positions grows (development, 07 §4). |
| `adaptability` | L | Settling into a new club after a transfer (temporary mood/competence drag). |
| `recovery_rate` | L | Fatigue recovery per rest day. |
| `development_rate` | L | Scales progression toward potential (07 §4). |

### 1.5 Ability, form and condition

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `ability_current` | `AbilityScore` | L | **Derived cache**: the best role fit's weighted attribute average (`ratings.compute_current_ability`). The sim never reads it — it reads the individual attributes. It exists for sorting, wage/value formulas and compact summaries; the richer, non-collapsed view is the derived `PlayerProfile` (§1.9). |
| `ability_potential` | `AbilityScore` ≥ current | L | Hidden ceiling for the development system (07 §4); occasionally revised for young players. Never visible to AI clubs directly — they see a noisy `ScoutReport`/perceived value. |
| `form` | `Unit` (0.5 neutral) | S+L | EMA of recent match ratings, exposed as a modifier on effective attributes (±4% max). |
| `form_history` | `list[float]` (last 10 ratings) | L | Source for the EMA; also commentary ("three goals in his last four"). |
| `morale` | `Unit` (0.5 neutral) | S+L | Modifier on work rate/composure (±3%). Updated post-match. |
| `morale_factors` | `list[MoraleFactor{kind, delta, expires_on}]` (≤12) | L | Explains *why* morale is what it is (benched, won derby, contract row). Future interview generation reads this. |
| `state_modifiers` | **separate table** `StateModifier` (see §11) | L → S via `PlayerSnapshot.mood` | Discrete, explainable, time-limited episodes ("had a terrible week") with capped effects on pitch performance. |
| `mood` (snapshot only) | `ResolvedMood{mental_mult, technical_mult, physical_mult, volatility_add, contributing_modifier_ids, public_storyline_keys}` | S | Output of `resolve_mood()` frozen into the `PlayerSnapshot`. |
| `training` | `TrainingPlan{focus: attribute_group\|position_retrain\|balanced, retrain_position: Position\|None, intensity: Unit}` | L | Individual training focus (club default overrides). |
| `development_log` | `list[DevelopmentEntry{date, attr, delta, cause}]` (last 24) | L | Why attributes changed; explainable for commentary/UI. |
| `status` | `active\|retired\|free_agent` | L | |
| `fitness` | `Unit` | S+L | Long-run conditioning; caps in-match energy. |
| `fatigue` | `Unit` (0 = fresh) | S+L | Accumulated tiredness carried into a match; sim starts the player at this value and **only increases it during play**. |
| `match_sharpness` | `Unit` | S+L | Rises with minutes, decays with inactivity; ±3% on touch/decisions. |
| `current_injury` | `Injury \| None` | S+L | `Injury{type, body_part, severity: knock\|minor\|moderate\|severe, started_on, expected_return_on, games_missed}`. Unavailable players are excluded from sheets. |
| `injury_history` | `list[InjuryRecord]` | L/R | Feeds proneness and storylines ("his fourth hamstring problem"). |
| `suspension` | `Suspension{matches_remaining, reason} \| None` | L | |
| `discipline` | `{yellows_season, reds_season, yellow_ban_threshold_progress}` | L | |

### 1.6 Contract, value, career, stats

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `contract` | `Contract` | L | Separate table in persistence (wage-bill queries). `Contract{club_id, start, end, wage_weekly, signing_bonus, appearance_bonus, goal_bonus, clean_sheet_bonus, release_clause: Money\|None, sell_on_pct, squad_role: key\|rotation\|prospect\|backup, extension_option: bool, relegation_wage_cut_pct}`. All fields are **L** now (07 §5–6): wage and bonuses flow through the ledger, release clauses can trigger transfers, `squad_role` is a playing-time promise (broken promises create mood modifiers), `relegation_wage_cut_pct` is R (no relegation yet). |
| `market_value` | `Money` | L | Derived cache (`valuation.market_value(player, date)`) from CA, PA, age, reputation, contract length. |
| `squad_status` | `first_team\|reserve\|youth\|loaned_out\|free_agent` | L | |
| `career_history` | `list[CareerStint{club_id, from, to, apps, goals}]` | L | Written by the transfer system (07 §6) on every move; seeded with plausible back-history. |
| `season_stats` | **separate table** `PlayerSeasonStats` keyed `(player_id, season_id, competition_id, club_id)` | L | `apps, starts, minutes, goals, assists, shots, shots_on_target, xg, xa, passes, passes_completed, key_passes, dribbles_won, tackles, tackles_won, interceptions, clearances, fouls_committed, fouls_suffered, yellows, reds, saves, goals_conceded, clean_sheets, rating_sum, motm`. **Career totals are computed** from season rows, never stored (no drift). |

### 1.7 Relationships, memories

Not embedded: see §6 (Relationship) and §7 (Memory). A player's "typed memory store" is the set of `MemoryRecord`s with `owner = EntityRef(player, id)`, partitioned by `MemoryKind`. Keeping memories out of the player row prevents unbounded row growth and makes the LLM-proposal boundary (04-architecture §4.4) trivial to enforce.

### 1.8 Player validators (property-tested with hypothesis)

`potential ≥ current`; `position_competence` has ≥1 value ≥ 85 for non-youth; GK has `GK ≥ 85` and outfield positions ≤ 30 (and vice versa); `height/weight` plausible; fatigue/fitness/morale within `Unit`; `current_injury.expected_return_on ≥ started_on`; attribute groups all present; age 15–45 on the reference date.

### 1.9 `PlayerProfile` — the "what is he good at?" view (derived, never stored)

A player is **not** one number. He is ~50 independent `Attribute`s, a map of position/role competences, a set of traits and hidden attributes. Two players with the same `ability_current` can be completely different footballers (a 74 poacher with elite finishing/composure and poor passing vs. a 74 ball-winner with elite tackling/work rate and poor finishing). `ratings.build_profile(player)` (pure) derives:

| Field | Meaning | Used by |
|-------|---------|---------|
| `group_scores` | weighted mean per group: `technical, mental, physical, goalkeeping` (and sub-groups: `attacking, defending, passing, creativity, athleticism`) | UI, squad analysis, transfer needs (L) |
| `role_ratings` | `dict[RoleAssignment, AbilityScore]` — fit for **every** role+duty (attribute-weighted per `roles.yaml`, scaled by position competence) | lineup AI, transfer AI, tactics (S/L) |
| `position_ratings` | best role rating per position | lineup AI (S) |
| `strengths` / `weaknesses` | attributes ≥ 1.0σ above/below position peers (z-scores against league distribution for his position), top 3–5 each | commentary/UI hooks (R), scouting (L) |
| `signature_skills` | rule-derived labels: `elite_finisher` (finishing ≥ 85 ∧ composure ≥ 70), `engine` (stamina ≥ 85 ∧ work_rate ≥ 80), `ball_playing_defender`, `aerial_threat`, `set_piece_specialist`, `speedster`, `playmaker`… | commentary/UI (R), transfers (L) |
| `archetype_label` | nearest named player archetype (e.g. "Poacher", "Anchor", "Inverted Winger") by attribute-profile distance | UI/LLM prompts (R) |
| `volatility_label` | from `consistency` and form variance ("streaky", "reliable") | UI/LLM prompts (R) |

**Generation consequence (05):** players are generated with *spiky* profiles by archetype (strong where the archetype demands, weak elsewhere) rather than uniform noise around a mean, and a test asserts profile dispersion (mean within-player attribute standard deviation ≥ 10 points; no archetype's signature attributes below its floor).

## 2. Manager

`Manager = Person + …`

| Group | Field | Type / range | Use | Rationale |
|-------|-------|--------------|-----|-----------|
| Philosophy | `style` | `possession\|counter_attacking\|high_press\|direct\|balanced\|low_block\|wing_play\|gegen_press` | S | Name tag; the real behaviour lives in the sliders below. |
| | `philosophy` | `Philosophy{possession_preference, directness, pressing_intensity, tempo, width, defensive_line, risk_taking, set_piece_focus, rotation_tendency, youth_trust}` all `Unit` | S (first 7) / L (rest) | Seeds the club's default `TeamTactics` and the AI manager's in-match baseline. |
| Formations | `preferred_formation` | `FormationId` | S | |
| | `fallback_formations` | `list[FormationId]` (≤3) | S | Candidate set for in-match shape changes. |
| | `formation_proficiency` | `dict[FormationId, Competence]` | S | Scales team cohesion/tactical-familiarity modifier; discourages exotic shape changes. |
| In-match | `flexibility` | `Unit` | S | Probability and speed of reacting to match state; adds latency jitter to review checkpoints. |
| | `substitution_habits` | `SubHabits{earliest_minute, preferred_windows: list[int], aggressiveness: Unit, fresh_legs_bias: Unit, protect_lead_bias: Unit, chase_game_bias: Unit, reacts_to_cards: Unit, uses_all_subs: bool}` | S | Drives `ai_manager.substitution_policy`. |
| | `touchline_behaviour` | `calm\|animated\|furious\|stoic\|theatrical` | R | Renderer/commentary flavour for manager reactions. |
| Attributes | `attributes` | `ManagerAttrs{tactical_knowledge, man_management, motivation, youth_development, judging_ability, judging_potential, adaptability, discipline, fitness_coaching, set_piece_coaching, negotiation, media_handling}` all `Attribute` | tactical_knowledge, adaptability, motivation, man_management, discipline = **S**; `youth_development` (L: development of young players), `judging_ability`/`judging_potential` (L: transfer-target perception noise), `negotiation` (L: transfers/contracts), `fitness_coaching` (L: recovery), `media_handling`, `set_piece_coaching` = R | See 02 §11 for exactly how each shapes the AI. |
| Personality | `personality` | `Personality` | R (S: `discipline`-adjacent only) | |
| Media | `press_style` | `PressProfile{tone: calm\|fiery\|dry\|charming\|evasive\|blunt, candour, deflection, blame_tendency, bold_claims, mind_games, humor: Unit}` | R | Press-conference generator input. |
| Reputation | `reputation` | `Reputation` | L | |
| Contract | `contract` | `ManagerContract{club_id, start, end, wage_weekly, release_clause, objectives: list[Objective]}` | L | |
| History | `career_history` | `list[ManagerStint{club_id, from, to, played, won, drawn, lost, trophies: list[TrophyRef]}]` | R/L | Seeded with plausible back-history; updated by the league layer going forward. |
| People | relationships | — | R | `Relationship` rows (player/board/media/rival-manager endpoints, §6). |
| Memory | memories | — | R | `MemoryRecord` rows (§7). |

## 3. Club (aggregate) and its parts

`Club` is an aggregate of small embedded models; heavy or high-churn parts (squad registration, ledger, staff, stats) are separate tables.

### 3.1 Identity

| Field | Type | Use | Rationale |
|-------|------|-----|-----------|
| `id`, `name`, `short_name`, `short_code` (3 letters, unique) | | L | `short_code` is accepted by the CLI in place of the id. |
| `nickname` | str | R | Commentary ("the Foxes"). |
| `colours` | `{primary, secondary, accent: hex, home_kit: KitSpec, away_kit: KitSpec}` | R (S: away kit clash check only) | Renderer. `KitSpec{pattern: solid\|stripes\|hoops\|halves\|sash, colours}` |
| `crest_description` | str | R | Text prompt for crest art. |
| `founded_year` | int | R | |
| `city`, `nation` | `{city, region, nation_id, population}` | L/R | Population ties to fanbase sizing; city climate band drives weather generation (L). |

### 3.2 Stadium (`Stadium`, embedded)

| Field | Type / range | Use | Rationale |
|-------|--------------|-----|-----------|
| `name`, `nickname` | str | R | |
| `capacity` | int 5 000–80 000 | S+L | Attendance ceiling; crowd-intensity denominator. |
| `pitch` | `Pitch{length_m 100–110, width_m 64–75, quality: Unit, surface: grass\|hybrid\|artificial, drainage: Unit, quirks: list[str]}` | S | Passing accuracy, injury hazard, rain response, familiarity; dimensions feed distance maths and "narrow/big pitch" home advantage. |
| `atmosphere` | `Unit` | S | Crowd effect multiplier (with attendance fill and fanbase passion). |
| `proximity` | `Unit` | S | How close the stands are; scales crowd effect and referee pressure. |
| `roof` | `open\|partial\|closed` | R | Weather interaction (later). |
| `altitude_m` | int | S | Small away-fatigue penalty at altitude. |
| `home_advantage` | `HomeAdvantageFactors{crowd_weight, referee_pressure_weight, familiarity_weight, travel_weight}` all `Unit` | S | Per-stadium *scaling* of each home-advantage channel (02 §8). Lets one stadium be a cauldron and another a library without touching the global config. |
| `ticket_price_base` | `Money` | L | Matchday income. |
| `upgrade` | `StadiumUpgrade{planned_capacity, cost, started_on, completes_on, status: none\|planned\|building}` | L/R | Capacity reduces during works (L). |

### 3.3 Fanbase

`Fanbase{size: int, passion: Unit, toxicity: Unit, fickleness: Unit, away_following: Unit, traditions: list[str]}`

- `passion` (S via stadium crowd effect, L attendance), `toxicity` (S: increases home-player pressure when losing; also affects away players' hostile-environment penalty; L: morale after bad results), `fickleness` (L: attendance elasticity to form), `away_following` (L: away attendance share; S: tiny away-support effect), `traditions` (R: chants/rituals as commentary/audio flavour).

### 3.4 Finances (`ClubFinances` state + append-only `LedgerEntry` table)

State (L): `balance: Money`, `wage_budget_weekly`, `transfer_budget`, `debt`, `debt_interest_rate: Unit`, `credit_limit`, `sponsor_deals: list[SponsorDeal{name, annual_value, ends_on}]`, `broadcast_share`, `last_reconciled_on`.

**Income streams** (ledger `category`): `matchday` (tickets × attendance + hospitality), `merchandise` (fanbase × passion × results), `sponsorship` (instalments), `broadcast` (equal share + merit by league position), `prize_money` (season end), `player_sales` (R). **Expenses**: `wages_players`, `wages_staff`, `facilities_upkeep`, `youth_academy`, `transfer_fees` (R), `debt_service`, `stadium_works`, `other`.

`LedgerEntry{id, club_id, date, category, amount (signed), counterparty: EntityRef|None, ref: {match_id|fixture_id|…}, memo_key}`. **Invariant:** `balance == opening_balance + Σ ledger.amount` (checked per club, and Σ over the league's inter-club entries nets to zero for transfers when those exist). The cached `balance` is only written by the repository in the same transaction as the ledger insert.

### 3.5 Facilities and academy

- `Facilities{training: Level, youth: Level, medical: Level, upgrades: list[FacilityUpgrade]}` — `medical` (L: shortens injury duration, in-match treatment time), `training` (L: development speed, recovery), `youth` (L: intake quality).
- `YouthAcademy{level: Level, intake_size: int, intake_quality: Unit, philosophy_tag: str, prospect_ids: list[PlayerId]}` — L (yearly intake, 07 §4.3). Youth prospects are ordinary `Player`s with `squad_status="youth"`; promotion to the senior squad is an AI decision. Youth *matches* are future scope.

### 3.6 Board and reputation

`Board{ambition: Disposition, patience: Disposition, meddling: Disposition, budget_strictness: Disposition, expectations: list[Objective], manager_confidence: Unit}` — L/R. `Objective{kind: league_position\|cup_round\|financial\|youth, target, deadline}`. `club_reputation: Reputation` (S: crowd/ref-pressure weight indirectly via away fear; L). `prestige: Reputation` (R: slow-moving historic standing).

### 3.7 Rivalries, history, culture, tactics

- `rivalries: list[Rivalry{club_id, intensity: Unit, origin: str, label: str}]` — **S+L**: `intensity ≥ 0.5` sets the `derby` flag on the fixture; the flag raises match intensity, foul/card rates (+), and `big_match` weighting.
- `history{trophies: list[TrophyRef{competition_name, season_label, count}], best_finish, records: list[ClubRecord], seasons: list[SeasonRecord{label, position, points}]}` — R (L: SeasonRecord appended at season end).
- `culture{values: dict[str, Unit]}` with keys `youth_focus, spending_pride, tactical_identity, discipline, media_openness, loyalty_to_manager, glamour, grit` plus `tags: list[str]` — R (S: `discipline` and `grit` nudge team cohesion 1–2%).
- `default_tactics: TeamTactics` — S. See §3.8.
- `staff_ids: list[StaffId]`, `manager_id` — L (relation).

### 3.8 TeamTactics — a versioned, module-based, extensible model (shared by Club defaults, TeamSheet, in-match changes)

**Design goal (revision 4):** the tactical vocabulary will keep growing (gegenpressing, passing triangles, rotations, overloads, pressing traps, named set-piece routines, per-player tendencies). So `TeamTactics` is **not a fixed bag of sliders**; it is a small core plus a **registry of tactic modules**. Adding a tactical idea = adding one module class (+ sim support behind a component) — no change to `TeamTactics`, the event schema's path-based diffs, the AI manager's patch mechanism, or the database.

```
TeamTactics                                   # frozen, schema_version: int
  formation: FormationId                      # nominal base shape
  structures: {in_possession, out_of_possession, rest_defence}: ShapeRef | None
                                              # shape per phase, e.g. 4-3-3 → 3-2-5 in possession, 4-4-2 out, 3-2 rest defence
  slots: list[SlotAssignment]                 # exactly 11: {slot, role: RoleId, duty: defend|support|attack}
  mentality: ultra_defensive|defensive|cautious|balanced|positive|attacking|all_out   # → risk −3..+3
  modules: dict[ModuleKey, TacticModule]      # the extensible part (below); absent module ⇒ module defaults
  player_instructions: list[PlayerInstruction]   # {slot, module, params}: per-player overrides of any module value
  situational: list[SituationalPlan]          # {when: Condition, apply: TacticsPatch, priority, cooldown_s}
  extensions: dict[str, JsonValue]            # namespaced experimental keys ("lab.my_idea"): stored, validated as JSON,
                                              # ignored by sims that do not know them
  roles_locked: bool                          # R
```

**`TacticModule`** = a frozen Pydantic model with `kind: Literal[...]` and its own `version`, discriminated in a union registered in `domain/tactics/modules/`. One concern per module (SRP). All sliders are `Unit`, enums for readable events and prompts.

| Module (`kind`) | Fields (v1) | Status |
|-----------------|-------------|--------|
| `build_up` | `goalkeeper: short\|mixed\|long`, `tempo`, `passing_directness`, `width`, `patience` | **S** |
| `final_third` | `shoot_on_sight`, `crossing_frequency`, `dribbling_freedom`, `focus: left\|centre\|right\|balanced`, `box_occupation` | **S** |
| `defensive_block` | `line_height`, `compactness`, `offside_trap`, `marking: zonal\|mixed\|man`, `tackling: stay_on_feet\|balanced\|aggressive` | **S** |
| `pressing` | `intensity`, `trigger: none\|ball_to_wide\|backpass\|loss_of_ball\|constant`, `press_line`, `cover_shadow` | **S** |
| `transitions` | `on_win: counter\|hold_shape\|slow_down`, `on_loss: counter_press\|regroup\|drop`, `counter_press_seconds` | **S** |
| `set_pieces` | `corner_routine`, `corner_attackers: 2..6`, `corner_defence`, `fk_routine`, `throw_in` | **S** |
| `game_management` | `time_wasting`, `foul_tolerance` | **S** |
| *planned, schema stubbed but unused by the v1 sim:* `support_geometry` (triangles/diamonds, support angles, rotations, third-man runs), `gegenpress` (regain window, zone triggers, trap side, recovery runs), `overloads` (zone overloads/isolations), `rest_defence` (numbers behind the ball), `positional_zones` (zone-by-zone player assignments), `set_piece_routines` (named, choreographed routines), `individual_tendencies` | **R** (08 §1) |

**Evolution rules:**
- **Versioning:** each module and `TeamTactics` carry a version; Pydantic migration functions upgrade stored tactics on read; unknown *modules* are preserved (round-tripped) but a sim only reads the modules it knows, via a `TacticsView` adapter that returns module defaults when absent — old tactics keep working in newer sims and vice versa (ISP/DIP: sim components depend on the view, not on the storage shape).
- **Situational plans** give the AI manager (and later learned policies) an expressive but bounded vocabulary: e.g. `when(score_state=leading ∧ minute≥70) apply(defensive_block.line_height−0.15, game_management.time_wasting+0.2)`. Applied patches are emitted as `tactical_change` events whose `changes[].field` is the module path (`modules.pressing.intensity`) — already how 03 describes them.
- **Instruction primitives** (what a module field can express) are validated against the module schema, so an LLM or learned policy can only propose *valid* tactics.
- **Data-driven presets:** named tactical styles (`gegen_press_4231`, `low_block_532`…) live in `data/static/tactic_presets.yaml` as full `TeamTactics` documents; the manager generator derives a club's defaults from `Manager.philosophy` + a preset.

Is this big enough for v1? It covers every behaviour the v1 sim (02) can express, in a structure that stays stable while the tactical vocabulary grows by an order of magnitude.

### 3.9 Squad registration and staff

- `SquadEntry{club_id, player_id, squad_number, status, squad_role}` — L (table `squad_entries`). Contract is the legal link, SquadEntry the practical one (number, status). Senior squad size 22–28 (target 25), plus youth.
- `StaffMember = Person + {club_id, role: assistant_manager|first_team_coach|goalkeeping_coach|fitness_coach|physio|scout|analyst|youth_coach, quality: Level, attrs: StaffAttrs{coaching_technical, coaching_mental, coaching_physical, tactical_input, injury_treatment, injury_prevention, scouting_judgement, scouting_network}, contract}`. Simple on purpose. Sim use: `assistant_manager.tactical_input` is a small bonus to the AI manager's decision quality (S); `physio.injury_treatment` shortens in-match stoppage and expected recovery (S/L); everything else is L/R.

## 4. Match Official (`Referee`)

`Referee = Person + …`

| Field | Range | Use | Rationale |
|-------|-------|-----|-----------|
| `strictness` | `Unit` | S | Foul-call threshold: how much contact is penalised. |
| `consistency` | `Unit` | S | 1 − decision noise; also shrinks drift across the match. Low consistency produces "he's lost control" games and bad offside/penalty calls. |
| `home_bias` | `Signed` (−0.2..+0.5 typical) | S | Tilt on marginal decisions (fouls, cards, 50/50 penalties) toward the home side, scaled by crowd pressure. |
| `card_tendency` | `Unit` | S | Yellow/red threshold shift independent of strictness (card-happy vs. talk-first). |
| `advantage_tendency` | `Unit` | S | Plays advantage vs. blowing the whistle. |
| `added_time_generosity` | `Unit` | S | Multiplier on stoppage-time calculation. |
| `penalty_propensity` | `Unit` | S | Willingness to give contact penalties. |
| `video_reliance` | `Unit` | S (M10) | Likelihood to self-initiate/accept a review. |
| `fitness` | `Unit` | S | Positioning quality → small decision-accuracy modifier late. |
| `reputation` | `Reputation` | R | |
| `temperament` | `Disposition` | R | Player-dissent handling, commentary colour. |
| `assistants`, `video_official` | `list[PersonRef]` | R | |

## 5. Commentators and media personalities

`MediaPersonality = Person + …` — **entirely R** in this task (no consumer yet), but fully seeded, validated, schema-exported, and persisted. Roles: `play_by_play`, `colour_analyst`, `pitchside_reporter`, `studio_presenter`, `pundit`.

| Group | Field | Type / range | Rationale |
|-------|-------|--------------|-----------|
| Role | `role`, `employer: str`, `experience_years` | | |
| Persona | `persona_summary` | str, deterministic template from archetype | One paragraph that the LLM layer can drop in a system prompt. |
| | `personality` | `Personality` | Shared traits (humor, ego, volatility…). |
| | `broadcast_traits` | `{enthusiasm, formality, analytical_depth, storytelling, sarcasm, empathy, risk_of_gaffe: Unit}` | The knobs that distinguish a measured analyst from a shouty enthusiast. |
| Speech | `speaking_style` | `SpeakingStyle{verbosity: Unit, sentence_length: short\|mixed\|long, vocabulary: plain\|rich\|technical\|colloquial, metaphor_domain: str, favourite_idioms: list[str]≤5, avoided_words: list[str], dialect_markers: list[str], filler_phrases: list[str]}` | Style-guide for the future prompt. |
| | `catchphrases` | `list[Catchphrase{id, text, trigger_tags: list[ContextTag\|EventType], min_gap_events: int, max_per_match: int}]` | Tags match the event context vocabulary (03 §3) so the Narrator can fire catchphrases mechanically. |
| Knowledge | `knowledge` | `dict[KnowledgeArea, Attribute]` with areas `tactics, club_history, youth, finance, statistics, fitness_medical, officiating, transfers, league_history` | What they can plausibly speak authoritatively about. |
| Bias | `biases` | `Biases{club_affinity: dict[ClubId, Signed], favourite_players: list[PlayerId], disliked_players: list[PlayerId], referee_attitude: dict[RefereeId, Signed], favourite_managers: list[ManagerId], disliked_managers: list[ManagerId], pet_peeves: list[str]}` | Explicit, inspectable partiality. |
| Emotion | `emotional_range` | `{baseline_energy: Unit, peak_energy: Unit, volatility: Unit, composure_under_drama: Unit, excitement_thresholds: dict[EventType\|ContextTag, Unit]}` | `excitement_thresholds` map directly onto `event.ctx.significance` so "when does he lose his voice" is data, not prompt text. |
| Chemistry | relationships | — | `Relationship` rows of kind `colleague\|feud\|mentor\|mentee\|friend` with `on_air_chemistry: Unit`, `running_jokes: list[RunningJoke{id, text, origin_memory_id\|None, last_used_on, uses}]`, `feud_topic`. See §6. |
| Voice | `voice` | `VoiceProfile` — **redesigned in revision 4; full spec and the provider decision are in `12-voice-and-tts.md`**: a provider-agnostic *casting sheet* (`gender`, `age_range`, `accent`, `timbre`, `register`, `base_pace_wpm`, `energy_range`, `delivery_notes`) plus `bindings: dict[ProviderId, VoiceBinding{voice_id, model, settings}]` so the same character can be re-cast on another provider without touching the persona, plus a pronunciation lexicon derived from `Person.pronunciation`. | Separates *who the character sounds like* (stable, ours) from *which vendor voice currently plays them* (swappable). |
| History | `broadcast_history` | `list[BroadcastRecord{match_id, role}]` | Appended by the future layer. |
| Memory | memories | — | `MemoryRecord` rows. Commentators remember refereeing howlers and old feuds too. |

A `BroadcastCrew{play_by_play_id, colour_id, pitchside_id, presenter_id, pundit_ids}` model is defined for `Match.crew` (R).

## 6. Relationship (shared across all entity kinds)

A separate entity — **not** embedded copies on each person — because relationships are symmetric, cross-type, and edited from both sides.

| Field | Type | Use |
|-------|------|-----|
| `id` | `Id` | |
| `a`, `b` | `EntityRef` (canonical order: `a.id < b.id` for symmetric kinds) | |
| `kind` | `friend\|rival\|mentor_of\|family\|teammate_bond\|colleague\|feud\|admires\|dislikes\|agent_of\|…` (directed kinds use a→b) | |
| `strength` | `Signed` (affinity) | S (teammate_bond/friend among XI: ≤ +1.5% pass-affinity, "chemistry"), else R |
| `intensity` | `Unit` | R |
| `on_air_chemistry` | `Unit \| None` | R (media pairs) |
| `running_jokes` | `list[RunningJoke]` | R |
| `since`, `last_updated`, `notes_tags` | | L/R |
| `source` | `fact\|seed\|proposed` | L |

Seed generation produces family pairs (brothers/father-son), friendships (shared nationality/age), mentor links (veteran → youth), rivalries (rivals-from-youth), manager–player trust, and media chemistry/feud pairs.

## 7. Memory (shared across characters) — schema only in this task

One record type for players, managers, staff, referees, media personalities, and (optionally) clubs. **No decay/retrieval/update logic is implemented now**; only the schema, repository CRUD, table, JSON Schema, and the Protocols that will use them.

```
MemoryRecord
  id: MemoryId
  owner: EntityRef                          # who holds this memory
  kind: MemoryKind                          # discriminates `payload`
  payload: MemoryPayload                    # discriminated union (below)
  summary: str                              # 1–2 sentence canonical text (deterministic template for facts)
  participants: list[EntityRef]             # who/what it involved
  tags: list[str]                           # open vocabulary: "derby","red_card","comeback","hat_trick","feud:ref_x2k"
  valence: Signed                           # −1 awful … +1 joyous, from the OWNER's perspective
  arousal: Unit                             # emotional intensity; slows decay
  importance: Unit                          # owner-relative significance at creation
  created_on: GameDate;  created_tick: int  # world date + match tick for ordering within a day
  last_recalled_on: GameDate | None;  recall_count: int
  decay: Decay{half_life_days: float, floor: Unit}   # floor>0 = "defining moment" never fully fades
  confidence: Unit                          # 1.0 = ground-truth fact; <1 for rumours / shaky recollection
  source: Source{origin: sim_fact|derived|proposed, match_id|None, event_ids: list[str], proposal_id|None}
  visibility: Visibility{scope: private|circle|team|public, circle: list[EntityRef]}
  status: active|archived|superseded;  superseded_by: MemoryId | None
  embedding_ref: str | None                 # R: pointer to a future vector store
  rev: int                                  # optimistic concurrency
```

`MemoryPayload` kinds: `MatchMoment{match_id, event_ids, role_in_event, headline}`, `Milestone{kind: debut\|first_goal\|hundredth_app\|hat_trick\|trophy\|first_win_as_manager…}`, `Interaction{with, setting: press\|dressing_room\|touchline\|tunnel, gist}` (LLM-origin), `RelationshipShift{relationship_id, delta, cause}`, `Opinion{about: EntityRef, stance, reasons}`, `Reflection{consolidates: list[MemoryId], theme}`, `SeasonSummary{season_id, bullets}`.

### 7.1 Planned dynamics (documented now, implemented later)

- **Strength** at time *t*: `strength = importance × max(floor, 0.5^(Δdays / H))` with `H = base_half_life(kind) × (1 + 2·importance) × (1 + 0.5·arousal) × (1 + 0.15·min(recall_count,5))`. Recalling a memory (`last_recalled_on`, `recall_count++`) reinforces it. Pure arithmetic — no RNG, so it is testable and reproducible.
- **Retrieval for an LLM prompt** (`MemoryRetriever`, later): input `RetrievalQuery{owner, situation_tags, entities_in_play, event_types, now, token_budget, audience_scope}`.
  1. Candidates = owner's `active` memories whose `visibility` is allowed for the audience (a commentator may only surface `public` memories about a player, never that player's `private` ones).
  2. Score = 0.35·relevance (entity/tag Jaccard overlap + optional embedding cosine) + 0.25·strength + 0.20·recency + 0.20·emotional salience (`|valence|·arousal`). Weights are configuration.
  3. Diversify with MMR to avoid ten near-duplicate goal memories.
  4. Pack into the token budget in three labelled blocks: **Defining moments** (high importance/floor, any age), **Recent** (≤ 14 days), **Relevant to now** (tag/entity matches), preceded by the owner's persona card and top relationships.
- **Summarisation:** when an owner has > N active low-importance memories in a window, a (future) LLM job *proposes* a `Reflection` consolidating them; the applier marks the sources `superseded` (never deletes) and links `superseded_by`. `EntityDigest{owner, text, built_from_hash, token_count}` (R) caches rolling summaries.
- **Writers:** deterministic code writes `source.origin = sim_fact|derived` memories from match results (facts); the LLM layer may only submit `Proposal`s (04 §4.4). Visibility/`confidence` stop an LLM-authored rumour from becoming "public knowledge" without an explicit rule.

## 8. Competition, Season, Fixture, Standings

| Entity | Fields | Use |
|--------|--------|-----|
| `Competition` | `id, name, short_name, kind: league\|cup, nation_id, tier, format: LeagueFormat\|CupFormat, prize_money: dict[position, Money], broadcast_pool: Money, match_rules: MatchRules` | L |
| `LeagueFormat` | `teams: int, rounds: 1\|2, points_win=3, points_draw=1, points_loss=0, tie_breakers: list[TieBreaker], promotion_spots, relegation_spots (R), qualification_spots (R)` | L |
| `MatchRules` | `subs_allowed=5, sub_windows=3, bench_size=9, regulation_minutes=90, extra_time: bool=False, shootout: bool=False, video_review: bool, yellow_ban_threshold=5` | S+L (passed into sim config) |
| `TieBreaker` | enum, order configurable: `points`, `goal_difference`, `goals_for`, `head_to_head_points`, `head_to_head_gd`, `wins`, `fair_play`, `seeded_draw` | L |
| `Season` | `id, competition_id, label, start_date, end_date, status: scheduled\|in_progress\|complete, club_ids, matchdays: list[MatchDay]` | L |
| `MatchDay` | `id, season_id, number, date, slots: list[KickoffSlot{local_time, fixture_id}]` | L |
| `Fixture` | `id, season_id, competition_id, matchday, home_club_id, away_club_id, kickoff: {date, local_time}, status: scheduled\|simulated\|broadcast_ready\|live\|completed\|quarantined\|postponed (10 §7), match_id\|None, is_derby, importance: Unit, broadcast_priority: int` | L (+S: `is_derby`, `importance` pass into the sim) |
| `StandingRow` | `season_id, club_id, played, won, drawn, lost, goals_for, goals_against, points, position, form_last5: str ("WWDLW")` | L — **derived** from completed fixtures by `standings.compute()`; also persisted as `StandingsSnapshot{season_id, after_matchday, rows}` for charts/commentary history. |

**Schedule generation** (`league/schedule.py`): circle method for a single round robin (7 matchdays for 8 clubs), mirrored with home/away swapped and the order of matchdays reshuffled for the second half; home/away alternation optimised to avoid more than 2 consecutive home or away games (deterministic local search from the seed); derbies steered away from matchday 1 and onto marquee slots; final matchday has simultaneous kickoffs. Result: 14 matchdays × 4 fixtures = 56 matches per season. Match-day structure: Saturday slots 12:30 / 15:00 / 15:00 / 17:30 (in-world time) by default; final round all at 15:00. The broadcast layer decides how in-world kickoff maps to channel time.

## 9. Match, TeamSheet, Weather

### 9.1 Weather (`Weather`) — S

`{condition: clear\|cloudy\|light_rain\|heavy_rain\|windy\|fog\|snow\|hot\|cold, temperature_c: −10..42, humidity: Unit, wind_speed_mps: 0..20, wind_direction_deg: 0..359, rain_mm_per_h: 0..30, pitch_wetness: Unit (derived), visibility: Unit, daylight: day\|dusk\|night}`. Generated deterministically per fixture from city climate band + date (L), then frozen onto the match. Effects: 02 §10.

### 9.2 TeamSheet (the frozen sim input per side) — S

```
TeamSheet
  club: ClubSnapshot{id, name, short_code, colours, reputation, rivalries_with_opponent: Unit}
  manager: ManagerSnapshot{id, name, philosophy, flexibility, sub_habits, attributes(subset), formation_proficiency, fallback_formations}
  assistant_tactical_input: Attribute
  physio_quality: Attribute
  lineup: list[LineupSlot{slot: 0..10, player_id, role, duty}]   # exactly 11
  bench: list[PlayerId]                                           # ≤ 9
  squad: dict[PlayerId, PlayerSnapshot]                           # everyone named above
  tactics: TeamTactics
  policy: {policy_id: str, policy_version: str}   # which ManagerPolicy made in-match decisions ("rules-v1" now; learned policies later, 08 §2)
  captain_id, penalty_takers: list[PlayerId], free_kick_takers: list[PlayerId], corner_takers: {left, right}
  fanbase: Fanbase subset; stadium: Stadium (home side only)
```

`PlayerSnapshot` = exactly the sim-relevant subset of `Player`: name/known_as, age, height, weight, foot, weak_foot, attrs (four groups + hidden), position_competence, role_familiarity, traits, form, morale, **mood (`ResolvedMood`, 07 §3)**, fitness, fatigue, sharpness, personality (`volatility`, `sportsmanship`), reputation, squad_number, and `public_storylines` (keys of public state modifiers, passed through to the kickoff preamble for the future narrator). **A snapshot, not a reference** — the sim cannot reach into a database, and the snapshot stored with the match makes any match replayable from its record alone.

### 9.3 Match (persisted record)

| Field | Use | Notes |
|-------|-----|-------|
| `id, fixture_id, competition_id, season_id, matchday` | L | |
| `date, venue_stadium_id, home_club_id, away_club_id` | L | |
| `weather: Weather`, `referee_id`, `attendance: int` | S | Attendance computed *before* the match by `league.attendance` and passed in. |
| `is_derby`, `importance`, `storylines: list[Storyline]` | S / R | `storylines` are pre-computed deterministic facts ("former club", "player on 99 goals") — R. |
| `home_sheet`, `away_sheet` | S | Snapshots; the kickoff event also embeds a compact lineup preamble. |
| `crew: BroadcastCrew \| None` | R | |
| `seed: int`, `config_hash: str`, `sim_version: str` | S | Replay key: **(sheets, seed, config) ⇒ identical event log**. |
| `status: scheduled\|completed`, `home_goals`, `away_goals`, `ht_home`, `ht_away`, `log_digest: sha256` | L | |
| `tactical_timeline` | S | Derived from `tactical_change`/`substitution` events (not duplicated in the record). |
| events | S | Rows in `match_events` (03-events). Ground truth. |

## 10. Reference/registry data (not entities, but versioned content)

`data/static/*.yaml`, validated at load by Pydantic and covered by tests: `formations.yaml` (8 formations, slot geometry), `roles.yaml` (≈30 roles × duties: offsets, attribute weights, utility biases), `traits.yaml`, `injury_types.yaml`, `name_cultures.yaml`, `archetypes.yaml` (player/manager/media/club archetypes), `climate.yaml`, `sim_config.default.yaml`, `balance_targets.yaml` (profiles, 02 §14), `mood.yaml` (state kinds, effect weights, caps), `development.yaml` (age curves per attribute group, retirement hazard), `transfer.yaml` (windows, negotiation constants). Details in 02, 05, 07.

## 11. World-state entities added in revision 2 (full definitions in 07)

| Entity | Purpose | Use |
|--------|---------|-----|
| `StateModifier` | Time-limited mood/life episode on a person (kind, magnitude, decay, source, visibility). Resolved into `ResolvedMood` before each match. | L → S |
| `WorldEvent` | Shared "news feed": transfers, bust-ups, awards, long injuries, retirements, records. Cited by modifiers; later narrated and memorised by the LLM layer. | L / R |
| `TransferWindow`, `TransferListing`, `TransferBid`, `ContractOffer`, `Transfer`, `ScoutReport` (+ synthetic `OUTSIDE_WORLD` counterparty) | Transfer market (07 §6). | L |
| `DevelopmentEntry`, `TrainingPlan` | Explainable attribute changes and training focus. | L |
| `ManagerKnowledge` | Reserved table for learned/adaptive manager experience (08 §2). | R |
