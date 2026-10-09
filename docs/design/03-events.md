# 03 — Event Schema

Status: **PROPOSED (Phase 1).** This is the cross-language contract. Python source of truth: `footystreams/events/`; exported to `schemas/events.schema.json` (+ `schemas/models/*.json`) by `uv run export-schemas`; a drift test fails CI if the committed schemas differ from regenerated ones. The future TypeScript frontend generates its types from these files.

## 1. Principles

1. **Discriminated union on `type`.** `MatchEvent = Annotated[Union[Kickoff, Pass, …], Field(discriminator="type")]`. Adding an event type is a minor schema bump; changing a field is a major bump. `schema_version` is a SemVer string (`SCHEMA_VERSION` in `footystreams.domain.versions`; initially `"0.1.0"`, promote to `"1.0.0"` after M2∥M4 exercise the contracts) on the match preamble and in every summary.
2. **Self-contained but light.** Events reference people by id; the **first `kickoff` carries a `preamble`** (rosters, names, shirt numbers, formations, weather, referee, attendance, derby flag) so a consumer can resolve ids without a database. No names in later events (they're derivable), *except* `ctx.headline` (short deterministic label, e.g. `"Brae (HAR) shoots"`) for debugging and the CLI.
3. **Causal context only.** Every event's `ctx` uses only information available *at that moment*. Hindsight facts ("this was the winner") live in the `fulltime`/`match_summary` events and in an optional non-causal annotation pass (§6). A live narrator must never see the future.
4. **Structured over textual.** Reasons, outcomes and flags are enums/booleans, not prose, so the commentary layer need not parse stats or guess motives.
5. **Everything has a position** where physically meaningful: normalised absolute `Pos{x,y}` in [0,1] (03 §2.3). Dead-ball events carry the restart position.
6. **Stable ids and order.** `id = "{match_id}:{seq:05d}"`; `seq` strictly increases from 0; ordering = `(seq)`. One sim *moment* may emit several events sharing `tick` and `t` (e.g. `shot → save`, `foul → card → free_kick`).

## 2. Base event

```python
class EventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str                      # "mch_x1:00042"
    match_id: MatchId
    seq: int                     # ≥0, strictly increasing
    tick: int                    # sim step counter (several events may share a tick)
    type: Literal[...]           # discriminator, set by each subclass
    clock: MatchClock
    team: Side | None            # acting team ("home"|"away") when meaningful
    participants: list[Participant]   # everyone involved, with role
    pos: Pos | None
    caused_by: str | None        # event id that directly led to this one (shot→save, foul→card)
    chain_id: int                # possession-sequence number (increments on possession change)
    ctx: EventContext
```

### 2.1 `MatchClock`
`{period: 1|2 (3|4 reserved for extra time), t: int, minute: int, added: int, display: str}`
`t` = elapsed *playing* seconds since kickoff, monotone across periods (half-time excluded); `minute` = 1-based display minute (clamped to 45/90 in stoppage), `added` = minutes beyond (0 normally), `display` = `"45+2'"`.

### 2.2 `Participant`
`{player_id: PlayerId, side: Side, role: ParticipantRole}`; roles: `actor, target, assister, fouled, fouler, tackler, carrier, keeper, shooter, scorer, receiver, offside_player, off, on, injured, booked, taker, deflector, blocker`. The first participant is the principal actor; typed fields on each event (e.g. `shooter_id`) duplicate the principal ids for ergonomic access — the redundancy is intentional, and a validator checks they agree.

### 2.3 `Pos`
`{x: float, y: float}` each in [0,1], 4 dp. Absolute orientation (see 01 §0.3). `ctx.attack_dir: +1|-1` tells which way the acting team attacks in this period.

### 2.4 `EventContext` — what the commentary layer reacts to

| Field | Type | Meaning |
|-------|------|---------|
| `score` | `{home:int, away:int}` | Score **after** this event (goal events show the new score; others unchanged). |
| `score_state` | `level\|home_leading\|away_leading` | |
| `lead_margin` | int (signed, home-positive) | |
| `phase` | `build_up\|progression\|final_third\|counter\|set_piece\|dead_ball` | |
| `momentum` | `Signed` (home-positive) | From 02 §5.5. |
| `intensity` | `Unit` | Game "heat" (shot rate, tackles/min, card density in a 5-min window). Drives broadcast energy. |
| `significance` | `Unit` | **How much this event matters** (deterministic rule: goal 1.0 base, shot xG, red card 0.9, big save, etc., modulated by tags). The narrator's thresholds (`excitement_thresholds`) compare against this. Passes are ≈ 0.02–0.15 so a consumer can filter to "key events" with `significance ≥ 0.25`. |
| `men` | `{home:int, away:int}` | Players on pitch. |
| `tags` | `list[ContextTag]` | See below. |
| `headline` | `str` | Terse debug label. |
| `attack_dir` | `1\|-1` | |

**`ContextTag`** (causal): `derby`, `high_stakes`, `late_game` (≥ 75′), `stoppage_time`, `last_minutes` (≥ 88′ or stoppage of H2), `opening_goal`, `equaliser`, `go_ahead_goal`, `extends_lead`, `consolation_goal`, `comeback_goal` (scoring team had been behind and now level/ahead), `against_run_of_play` (scoring side's 15′ xG share < 30%), `brace`, `hat_trick`, `penalty`, `own_goal`, `man_advantage`, `ten_men`, `second_yellow`, `big_chance`, `big_save`, `woodwork`, `near_miss`, `goal_disallowed_check`, `first_touch_of_sub` (sub scores within 10′ of entering), `captain_involved`, `former_club` (from storylines, R), `milestone` (R), `rivalry_flashpoint` (foul/card between flagged derby players), `injury_scare`, `time_wasting`, `pressure_period` (one side's xG share > 75% over 10′).

Late-winner, comeback-completed and similar hindsight facts: see §6.

## 3. Event catalogue

Notation: `field: type` — only the type-specific fields are listed; base fields always present. `Outcome` enums are closed. "R" = reserved/optional.

### Match structure
| `type` | Fields |
|--------|--------|
| `kickoff` | `reason: match_start\|second_half\|after_goal`, `kicking_team: Side`, `preamble: MatchPreamble \| None` (only on `match_start`). `MatchPreamble{schema_version, sim_version, config_hash, seed, home: TeamPreamble, away: TeamPreamble, referee: {id, name, strictness_label}, weather: Weather, attendance, capacity, is_derby, importance, competition, matchday, storylines: list, rules}`. `TeamPreamble{club_id, name, short_code, colours, formation_id, tactics_summary, manager:{id,name}, lineup:[{slot, player_id, name, shirt, position, role, duty, storylines: list[str]}], bench:[{player_id,name,shirt,position,storylines}]}` — `storylines` are the **public** mood keys (e.g. `"difficult_week"`, `"new_contract_glow"`, `"derby_hero"`) from 07 §3; private state modifiers still affect play but are never exposed. |
| `frame` | **Opt-in tracking snapshot** (`SimConfig.emit_frames`, default off; every `frame_interval_s`, default **1 s** of match time when on — chosen for smooth rendering; frames are deterministic interpolations and consume no RNG, so enabling them never changes any other event; a player never moves faster than a sprint (9 m/s) between frames, so one the sim places far away is shown running there, and `carrier_id` is `None` until the carrier is within 2.5 m of the ball): `players: list[{player_id, pos: Pos, speed: float, vx, vy, exhaustion: Unit}]` (22 entries, slot order; `vx`, `vy` are the metres per second over the last interval, along and across the pitch), `ball: {pos: Pos, carrier_id\|None, height_m}` (`ball_height_m`: above the grass, a parabola for a pass over 15 m, zero otherwise), `phase`, `shape: {home: ShapeMetrics, away: ShapeMetrics}` (line heights, width, compactness). Enables heatmaps, shape/pressing analysis and renderer movement; excluded from the digest unless frames are enabled (the digest records `frames: bool`). |
| `added_time` | `period`, `minutes: int`, `basis: {substitutions, injuries, goals, cards, reviews, time_wasting}` (seconds each) |
| `halftime` | `score`, `stats: TeamStatsPair`, `team_talks: {home: TeamTalk, away: TeamTalk}` where `TeamTalk{style: calm\|fiery\|tactical\|praise\|criticise\|motivate\|silent, morale_delta: float}`, `fatigue_snapshot: {side: [{player_id, exhaustion}]}` (the only place fatigue decreases is the declared half-time recovery, recorded here) |
| `fulltime` | `score`, `ht_score`, `result: home_win\|draw\|away_win`, `duration_s`, `added: {h1:int,h2:int}`, `attendance`, `winning_goal_event_id: str\|None`, `late_winner: bool`, `comeback: bool`, `biggest_lead_blown_by: Side\|None` — **hindsight allowed here** |
| `match_summary` | see §5 |

### Open play
| `type` | Fields |
|--------|--------|
| `pass` | `passer_id, receiver_id` (intended), `kind: short\|long\|through\|cross\|cutback\|switch\|back\|header\|lofted`, `outcome: complete\|intercepted\|out_of_play\|blocked\|offside\|overhit`, `end_pos: Pos`, `length_m: float`, `progressive: bool`, `key_pass: bool` (the pass directly led to a shot — set on the pass event only retroactively via the shot's `assist_id`, so on the pass it is `False` and shot carries truth; see note), `under_pressure: Unit`, `xt_gain: float`. |
| `dribble` | `player_id`, `outcome: success\|dispossessed\|fouled\|out_of_play`, `end_pos`, `distance_m`, `beaten_player_id\|None`, `skill_move: knock_past\|step_over\|drag_back\|cut_inside\|nutmeg\|roulette\|rainbow_flick\|None` (how the take-on was done, chosen from the dribbler's dribbling, flair, agility, balance and pace and the defender's distance, the pressure and the carrier's width; a look for the renderer, never an input to the outcome; `None` is a plain run) |
| `tackle` | `tackler_id, carrier_id`, `outcome: won\|lost\|foul`, `won_possession: bool`, `foul_event_id\|None` |
| `interception` | `player_id`, `passer_id`, `intended_receiver_id`, `kind: read\|block\|cut_out` |
| `clearance` | `player_id`, `under_pressure: Unit`, `outcome: out_of_play\|to_teammate\|to_opponent\|keeper_claimed`, `end_pos` |
| `shot` | `shooter_id`, `assist_id\|None` (key passer), `second_assist_id\|None`, `kind: open_play\|header\|volley\|long_range\|one_on_one\|tap_in\|free_kick\|penalty\|rebound\|counter`, `body_part: left\|right\|head\|other`, `xg: Unit`, `outcome: goal\|saved\|blocked\|off_target\|woodwork\|wide_high`, `target: GoalMouthPos\|None` (`{u,v}` in [0,1]: horizontal & vertical placement, for the renderer), `defender_pressure: Unit`, `blocker_id\|None`, `big_chance: bool`, `from_set_piece: none\|corner\|free_kick\|throw_in` |
| `save` | `keeper_id, shooter_id, shot_event_id`, `kind: catch\|parry\|tip_over\|tip_wide\|punch\|foot_save`, `outcome: held\|parried_safe\|parried_rebound\|corner_conceded\|goal_kick`, `psxg: Unit` (post-shot xG: difficulty), `big_save: bool` |
| `goal` | `scorer_id, assist_id\|None, second_assist_id\|None, shot_event_id\|None, kind: open_play\|header\|long_range\|free_kick\|penalty\|own_goal\|counter\|set_piece\|rebound, own_goal: bool, scoring_side: Side, credited_player_id, status: confirmed\|under_review, goal_number: int (match), scorer_goal_count: int, chain_passes: int, solo: bool, xg: Unit` — `score` in ctx is **after** the goal. |
| `offside` | `player_id` (flagged), `passer_id`, `margin_m`, `line_x`, `free_kick_pos` — `false_flag: bool` (R: wrongly flagged, for VAR drama) |

### Discipline & interruptions
| `type` | Fields |
|--------|--------|
| `foul` | `committer_id, fouled_id, kind: tackle\|trip\|push\|hold\|late_challenge\|handball\|dangerous_play\|obstruction\|dissent\|simulation\|time_wasting`, `severity: Unit`, `in_box: bool`, `outcome: free_kick\|penalty\|advantage_played\|play_on`, `denies_goal_opportunity: bool` |
| `card` | `player_id, colour: yellow\|red`, `reason: foul\|persistent\|dissent\|time_wasting\|denying_opportunity\|violent_conduct\|second_yellow\|handball_goalline`, `yellow_count_after: int`, `ban_matches: int` (reds), `men_after: int`, `foul_event_id\|None` |
| `injury` | `player_id`, `cause: contact\|non_contact\|foul`, `body_part`, `apparent_severity: looks_minor\|needs_treatment\|looks_serious`, `can_continue: bool`, `stoppage_s: int`, `caused_by_player_id\|None`. **True diagnosis is not in the event** — only in `match_summary.injuries` (a live narrator cannot know it). |
| `substitution` | `side, player_off_id, player_on_id, slot: int, reason: injury\|fatigue\|tactical\|protect_lead\|chase_game\|red_card_reshape\|yellow_risk\|poor_performance\|time_wasting, window: int (0 = half-time), subs_used_after: int, position_change: Position\|None, new_role: RoleAssignment\|None, initiated_by_manager_id` |
| `tactical_change` | `side, manager_id, changes: list[{field: str, from: Any, to: Any}]` (field names are tactics paths, e.g. `out_of_possession.line_height`), `formation_from\|None, formation_to\|None`, `reason: chasing_game\|protecting_lead\|red_card_response\|opponent_threat\|fatigue_management\|momentum_shift\|half_time_adjustment`, `trigger_event_id\|None` |
| `review` | **Video review (optional; recommended in M10).** `trigger: goal_check\|penalty_check\|red_card_check\|mistaken_identity`, `subject_event_id`, `duration_s`, `outcome: upheld\|overturned\|no_change`, `overturn_reason\|None: offside\|foul_in_build_up\|handball\|not_a_foul\|clear_foul\|…`, `score_after_review`. If a goal is overturned, ctx.score reverts. |

### Dead balls / restarts
| `type` | Fields |
|--------|--------|
| `throw_in` | `taker_id`, `kind: quick\|long\|short`, `side_of_pitch: top\|bottom` |
| `goal_kick` | `taker_id` (usually GK), `kind: short\|long` |
| `corner` | `taker_id`, `corner_side: top\|bottom`, `delivery: inswinger\|outswinger\|short\|driven\|floated`, `attackers_in_box: int`, `defenders_in_box: int`, `target_zone: near\|central\|far\|edge` |
| `free_kick` | `taker_id`, `kind: direct_shot\|cross\|short\|pass\|quick`, `distance_to_goal_m`, `wall_size: int`, `foul_event_id` |
| `penalty` | `taker_id, keeper_id, awarded_for_event_id`, `outcome: goal\|saved\|missed\|woodwork`, `placement: GoalMouthPos`, `xg: Unit` — followed by `goal` or `save` (and the shot-level fields are on this event; no separate `shot`) |

### Reserved in v1 schema (type names reserved, not emitted in this task)
`shootout_kick`, `extra_time_start`, `weather_change`, `crowd_reaction`, `manager_reaction` (touchline), `var_check_started`.

## 4. Sequencing rules (tested)

- `kickoff(match_start)` is `seq=0`; `fulltime` then `match_summary` are the last two events.
- `shot(outcome=goal)` is immediately followed by `goal` (same `t`); `shot(outcome=saved)` by `save`; `penalty(goal)` by `goal`.
- `foul` precedes its `card`, `free_kick`/`penalty`; `substitution` comes after the stoppage event that triggered it (`injury`, etc.).
- A goal that will be reviewed is emitted with `status=under_review`, followed (≥ 50 s later in `t`) by `review`. **Score at any point = Σ goals with `status=confirmed` or whose review outcome is `upheld`/`no_change`** (invariant tested). Un-reviewed goals are `confirmed` immediately.
- No event after `fulltime` except `match_summary`. After a red card or substitution the player id never appears again in any `participants` list (the "removed players stop generating events" invariant).

## 5. `match_summary`

`{schema_version, sim_version, config_hash, seed, log_digest, result, score, ht_score, attendance, duration_s, team_stats: {home, away}, player_stats: list[PlayerMatchStats], ratings: list[PlayerRating], player_of_the_match: PlayerId, goals: [...], cards: [...], substitutions: [...], injuries: [InjuryReport{player_id, type, body_part, severity, expected_return_days}], momentum_timeline: [{t, momentum}], xg_timeline: [{t, home, away}], key_moments: [{event_id, kind, significance, t}], narrative_hooks: list[Hook], formations_used, tactical_changes: [...]}`

- **Analytics-ready (pass maps, xG, networks):** `team_stats` and `player_stats` include `pass_matrix` (completed passes passer→receiver counts per team), `zone_pass_flow` (12×8 grid origin→destination counts), `shot_map` (list of `{event_id, pos, xg, outcome}`), and `xg/xa/xt` totals, all derived from the log and recomputable by `analytics/`; they are included in the summary so consumers need not re-scan 1,000+ events.
- `TeamStats`: possession %, shots, shots on target, xG, passes, pass accuracy, key passes, dribbles won, tackles/won, interceptions, clearances, fouls, offsides, corners, yellow/red, saves, big chances, field-tilt %, PPDA-style press metric, distance index.
- `PlayerMatchStats` (the unit the league layer folds into `PlayerSeasonStats`): minutes, starts, position played, goals, assists, shots, SoT, xG, xA, passes, completed, key passes, progressive passes, dribbles, tackles, interceptions, clearances, fouls, fouled, cards, saves, goals conceded, clean sheet, `end_exhaustion`, `injured: bool`.
- **Ratings** (`PlayerRating{player_id, rating: 3.0–10.0, breakdown: dict}`): start 6.0; add position-weighted contributions: goals (+0.9, +0.6 for GKs/defenders' rare ones), assists +0.55, xG/xA contribution above expectation, key passes, successful dribbles/tackles/interceptions (position-weighted), pass accuracy vs. expectation, saves above expected (psxg), clean sheet (+0.3 GK/DF), errors leading to shot/goal (−0.4/−0.8), cards (−0.3/−1.0), team result (±0.25), minutes scaling (players < 20 min regress toward 6.0). Clamped [3.0, 10.0], rounded to 0.1. Pure function of the events — recomputable from the log.
- `Hook{kind: late_winner|comeback|upset|hat_trick|red_card_turning_point|goalkeeper_heroics|dominant_unrewarded|debut_goal|derby_result|unbeaten_run_ended|…, event_ids, magnitude, text_key}`: deterministic story seeds for the narrator/memory layers (`text_key` is a template key, not prose).
- `log_digest`: sha256 of canonical NDJSON of all prior events.

## 6. Non-causal annotation pass (optional, separate artifact)

`annotate(events) -> list[EventAnnotation]` (post-hoc, stored in its own table, not in the event): `{event_id, is_winning_goal, was_turning_point, is_late_winner, comeback_completed, goal_of_the_match, narrative_weight}`. Needed for replays, highlight reels and memory creation (which run after the match). The live narrator never reads it.

## 7. Example (abridged, valid shape)

```json
{"id":"mch_7k2:00412","match_id":"mch_7k2","seq":412,"tick":371,"type":"shot",
 "clock":{"period":2,"t":3611,"minute":61,"added":0,"display":"61'"},
 "team":"home","participants":[{"player_id":"plr_a81","side":"home","role":"shooter"},
                                {"player_id":"plr_a2c","side":"home","role":"assister"}],
 "pos":{"x":0.8731,"y":0.4412},"caused_by":"mch_7k2:00411","chain_id":88,
 "shooter_id":"plr_a81","assist_id":"plr_a2c","second_assist_id":null,"kind":"open_play",
 "body_part":"right","xg":0.2144,"outcome":"goal","target":{"u":0.82,"v":0.31},
 "defender_pressure":0.31,"blocker_id":null,"big_chance":true,"from_set_piece":"none",
 "ctx":{"score":{"home":1,"away":1},"score_state":"level","lead_margin":0,"phase":"final_third",
        "momentum":0.34,"intensity":0.71,"significance":0.78,"men":{"home":11,"away":10},
        "tags":["big_chance","man_advantage","derby","late_game"],"headline":"Brae (HAR) shoots","attack_dir":1}}
```
(then `goal` at `seq` 413 with `tags:["go_ahead_goal","man_advantage","derby"]` — and the `score` after being 2–1.)

> Note on `key_pass`: because events are causal, the pass cannot know it will lead to a shot. The shot's `assist_id` is the truth; the pass's `key_pass` flag is set at pass time only when the *very next* action in the same tick is the shot (the sim resolves pass+shot as one moment for through-ball chances), otherwise it is `false` and consumers join on `assist_id`.

## 8. Schema export and versioning

The engine's outbound feed (13 §3) wraps match events: `BroadcastEvent = MatchEvent | SegmentEvent | WorldNotice | EngineMarker`, exported to `schemas/broadcast.schema.json`. `MatchEvent` is unchanged; segments (`pre_match`, `half_time`, `post_match`, `matchday_magazine`, `filler`) and `resume`/`restart` markers carry the structured facts future layers need.

`uv run export-schemas` writes `schemas/events.schema.json` (union `MatchEvent` with `discriminator`), `schemas/match_summary.schema.json`, `schemas/match_result.schema.json`, and one file per domain model under `schemas/models/`. `SCHEMA_VERSION` is a constant in `footystreams.domain.versions`; the drift test compares regenerated vs committed bytes (canonical JSON via `footystreams.domain.canonical`). A changelog `schemas/CHANGELOG.md` records version bumps. Floats are numbers with documented ranges (`minimum`/`maximum`), enums as `enum`, ids with `pattern`.

## 8. Implementation notes (Track A, M7)

The frozen M1 models are slimmer than section 3, so M7 adds fields **additively with defaults** (`SCHEMA_VERSION` 0.2.0): the causal `ContextTag` members, `pass.end_pos` / `progressive` / `xt_gain`, `dribble.end_pos`, `shot.big_chance`, `frame.carrier_id` and `frame.players`, the counting stats on `TeamStats` and `PlayerMatchStats`, `PlayerRating.breakdown` and the analytics rows of `MatchSummary` (`events/summary_rows.py`). `SCHEMA_VERSION` 0.4.0 adds how a shot travels for the renderer: `shot.target` (where the ball ends up, an absolute pitch `Pos`, not the `GoalMouthPos` above, so a block or a miss has an end point too), `curve` (-1..1, the side the path bows toward), `speed_mps` and `loft` (0..1). They come from the separate `flight` stream (`sim/flight.py`), so no other draw moves, and exist only with the context on. Not added: the per-event `kind` enums, `second_assist_id`, `shape` metrics on frames, the lists `goals` / `cards` / `substitutions` / `tactical_changes` / `formations_used` in the summary (scan the log), and `ctx.score_state` (derive from the scores).
