# Schema changelog

- 0.3.1: default `sim_version` in events/summary/result is now 0.4.1 (Track B rebase onto main; match output stamp only).
- 0.3.0: add world record and static-table models (Nation, City, SquadEntry, WorldManifest, Formation, TraitDefinition, InjuryType and their catalogs); purely additive, no existing model changed.
- 0.2.0: default `sim_version` is now 0.4.0 (M7 summary, ratings, context, frames). M7 additions, all with defaults. `ContextTag` gains the causal tags (derby, late_game, equaliser, go_ahead_goal, ...); `pass` gains `end_pos`, `progressive`, `xt_gain`; `dribble` gains `end_pos`; `shot` gains `big_chance`; `frame` gains `carrier_id` and `players` (`FramePlayer`); `TeamStats` and `PlayerMatchStats` gain the counting stats; `PlayerRating` gains `breakdown`; `MatchSummary` gains `injuries`, `momentum_timeline`, `xg_timeline`, `key_moments`, `hooks`, `pass_matrix`, `zone_pass_flow`, `shot_map` (rows in `events/summary_rows.py`).
- 0.1.6: default `sim_version` in events/summary/result is now 0.3.0 (M6 fatigue, injuries, weather, AI manager); no field changes.
- 0.1.5: default `sim_version` in events/summary/result is now 0.2.0 (M5 dead balls and discipline); no field changes.
- 0.1.4: default `sim_version` in events/summary/result is now 0.1.1 (SIM_VERSION bump); no field changes.
- 0.1.3: default `sim_version` in events/summary/result is now 0.1.0 (first simulator, SIM_VERSION bump); no field changes.
- 0.1.2: export every discovered domain `DomainModel` (usage registry auto-discovery).
- 0.1.1: model description updates (SubHabits / RoleDutySpec docs); regenerations stay in sync with domain.
- 0.1.0: initial export from M1 domain/events models.
