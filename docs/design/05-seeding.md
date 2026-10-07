# 05 — Seed Data Plan

Status: **PROPOSED (Phase 1).** Goal: `uv run seed --seed N` regenerates, byte for byte, a believable, fully fictional world that is internally coherent, varied, and immediately playable.

## 1. Outputs and reproducibility

```
data/worlds/<name>/                 # default name: "seed-<N>"; the committed one is "default" (seed 1)
  manifest.json                     # {world_seed, generator_version, schema_version, counts, content_sha256, created_in_world: "2031-07-01"}
  nations.json  cities.json
  competitions.json  seasons.json   # the first season, scheduled
  clubs.json  squad_entries.json  contracts.json
  players.json  managers.json  staff.json
  referees.json  media.json
  relationships.json  memories.json # memories: empty array in this task (schema only)
  ledger_opening.json               # opening-balance entries so the ledger invariant holds from day 0
```

- Canonical JSON (sorted keys, 2-space indent, trailing newline, LF endings even on Windows) so diffs are reviewable and the content hash is stable.
- **YAML only for hand-authored static tables** (`data/static/*.yaml`); generated worlds are JSON.
- The generator is a pure function `generate_world(seed, GeneratorConfig) -> World`; `seed` CLI writes it (`--out`, `--name`, `--db league.sqlite` to also load into SQLite, `--validate` to run only the coherence checks, `--clubs 8`). A test generates seed 1 and byte-compares against the committed `default` world.
- All randomness: `SimRng(seed).fork("world")` → sub-streams per generator (`names`, `clubs`, `players:<club>`, `managers`, `media`, `referees`, `relationships`) so adding a new generator step does not reshuffle existing output.

## 2. The league: 8 clubs

One fictional nation, **Valmere**, with an 8-club top division (**Valmere Premier League**; a cup schema exists but is not generated). Eight clubs in a double round robin gives 14 matchdays × 4 matches = 56 matches per season, which fits a 24/7 channel (one match ≈ 100 minutes of airtime, ~7 hours per matchday if shown in full, ≈ 4 days per season).

Club generation is archetype-driven so that the league has *shape*: a spread of strength, money, style and drama. Archetypes (assigned once each, shuffled by seed):

| # | Archetype | Reputation | Mean XI quality (0–100 team rating) | Money | Style tendency | Drama hook |
|---|-----------|-----------|-------|-------|----------------|-----------|
| 1 | **The Giants** | 85–92 | 72–76 | very high, big stadium | possession/high press | Expectations: nothing less than the title; impatient board |
| 2 | **The Challengers** | 75–82 | 68–72 | high | high press / wing play | Rich-ish rivals of the Giants; derby pair with #1 |
| 3 | **Old Money** | 70–78 | 64–68 | medium, ageing stadium | balanced, direct | Traditions, fading glory, big fanbase |
| 4 | **The Counter-Punchers** | 60–68 | 62–66 | medium | counter-attacking/low block | Tactical, well-coached, cards |
| 5 | **The Academy** | 55–65 | 58–62 | low-medium, top youth facilities | possession, young squad | Great prospects, unreliable |
| 6 | **Boom & Bust** | 50–60 | 58–64 (volatile) | in debt, high wages | attacking | Financial trouble, hot-headed manager |
| 7 | **The Grafters** | 45–55 | 54–58 | low | direct, physical | Hostile small ground (home-advantage monster), high fouls |
| 8 | **The Minnows** | 35–45 | 50–55 | very low, small stadium | low block / long ball | Plucky underdogs; upset generator |

Target league structure: best-vs-worst team rating gap ≈ 22 points (→ favourites win ~70–75% at that gap, consistent with the balance targets), median gap between adjacent clubs ≈ 3 points so the table is genuinely contestable. Two natural derby pairs (1–2; 3–7) plus one lighter rivalry (5–6).

**Names, places, colours.** Cities are generated from a Valmere place-name grammar (§4) with a population draw (weighted by archetype); club names combine city/district + a suffix from a small pool (`United`, `Athletic`, `Rovers`, `Albion`, `Town`, `Wanderers`, `Sporting`, `Harriers`…) with a uniqueness and distinctness check (different first letters, no near-duplicates by edit distance). Colours: curated palette pairs (primary/secondary/accent), kit pattern drawn so no two home kits clash; away kits chosen to contrast with every other home kit. `crest_description`, `nickname` are assembled from the city/colour/archetype with templates ("a rearing stag over three blue wavy lines"). Stadium names: neighbourhood/benefactor/founder templates; capacities drawn by archetype (e.g. Giants 52–62k, Minnows 8–12k); pitch quality/atmosphere/proximity correlated sensibly (small old grounds: high atmosphere & proximity, mediocre pitch).

## 3. Entities from the generators

### 3.1 Squads (≈ 33 per club, 264 players)

Per club: **25 senior** (3 GK, 8 DF [2 RB, 2 LB, 4 CB], 9 MF [3 DM/CM, 3 CM, 3 AM/wide], 5 FW) + **8 youth/reserve** prospects. Rules: every formation slot of the club's preferred formation and its fallbacks is *coverable* by ≥ 2 players with competence ≥ 70 (generation fails/rerolls otherwise); at least one back-up for each of LB/RB/CB/DM/ST; bench of 9 can always be formed with ≥ 1 GK.

**Producing one player (coherent, not uniform noise):**
1. Choose position, age (distribution: mean 26.8, σ 4.2, truncated 17–37; GKs +2 yrs; academy 16–19) and a *target ability* `CA*` from the club's archetype quality, position depth (starters higher than backups) and age curve.
2. Choose a **player archetype** from `archetypes.yaml` for that position (e.g. CB: `stopper`, `ball_playing`, `cover`; ST: `poacher`, `target_man`, `complete`, `pressing`; W: `inverted`, `classic`, `inside_forward`; GK: `traditional`, `sweeper`). Each archetype is a vector of attribute *biases* (e.g. stopper: tackling +12, marking +10, heading +10, pace −6, passing −5) plus preferred roles, traits and typical heights.
3. Sample attributes (**spiky, not flat** — a player is good at different things; see `PlayerProfile`, 01 §1.9): `attr = clamp(CA* + archetype_bias + latent_group_factor + noise)`; correlated latent factors (athleticism drives pace/acceleration/stamina/jumping with realistic correlation; technique drives touch/dribble/passing; football-IQ drives vision/decisions/anticipation/positioning). A fix-up loop rescales so that the recomputed role-weighted ability matches `CA*` within ±1.
4. **Position competence:** natural position 92–100; related positions at 60–85 by an adjacency graph (CB↔DM, RB↔RWB, CM↔DM/AM, W↔AM/ST, …) scaled by `versatility`; unrelated 0. Roles: preferred roles from the archetype with familiarity 75–100; others 20–55.
5. **Potential:** `PA = CA + growth(age)` (young: +5…+25; prime: 0–4; vets: 0), capped at 100; for the Academy club prospects are skewed high.
6. **Hidden attributes:** Beta-distributed (e.g. consistency ~ Beta(5,3)·100; injury_proneness ~ Beta(2,4)·100; dirtiness correlated with aggression/archetype), with a few deliberately extreme characters (a "streaky genius": high flair, low consistency; an "iron man": low proneness; a "dirty enforcer").
7. **Personality:** latent "temperament/ambition/social" factors → 10 trait values + `archetype_tags` + `interview_style` by rules (e.g. high ego & low humility → `cocky`). Veterans slightly more professional; academy kids less so.
8. **Bio:** nationality (club-region weighted: 70% Valmerian regional cultures, 30% foreign nations), name by culture grammar (§4), birthplace from a city list for that nation, height/weight from position-conditioned distributions with BMI sanity, foot (left 24%, both 6%) with weak foot 15–85 (higher for "both"), appearance spec.
9. **Condition at t0:** fitness 0.80–0.97, fatigue 0.0–0.1, sharpness 0.6–0.9, morale 0.45–0.65, form 0.5±0.05, 2–4% start with a minor injury.
10. **Contract & value:** `market_value = f(CA, PA, age, reputation)`; `wage_weekly ∝ value^0.8·archetype factor`; length 1–5 yrs (younger/prospects longer); bonuses/clauses drawn from simple rules. **Club wage bill is then scaled/adjusted so Σwages ≈ 85–105% of the club's weekly wage budget** (iterative: re-roll the most overpaid depth players first). Boom & Bust gets >100% on purpose.
11. **Stats at t0:** empty current season, plausible `career_history`/previous-season rows (R).

### 3.2 Managers (8 + 4 unemployed in the pool)

Each club's manager is matched to the club's archetype with intentional imperfection (a 20% chance of "mismatch" for drama). Generation: choose style → philosophy sliders from a style prototype ± noise; 1 preferred + 2–3 fallback formations drawn from a style-compatible set; `formation_proficiency` high for preferred, tapering for others; attributes drawn around a quality level correlated with club reputation but with *specialist spikes* (a tactician with weak man-management; a motivator with limited tactical depth); personality/press style by rules; age 38–66, career history of 2–4 plausible stints (clubs from a "wider world" list of fictional clubs); contract; and `substitution_habits` from style (e.g. conservative: late, protect-lead bias high).

**Tactics presets.** `data/static/tactic_presets.yaml` holds full `TeamTactics` documents (e.g. `gegen_press_4231`, `low_block_532`, `possession_433`, `wing_play_442`); a club's default tactics = the manager's best-matching preset adjusted by `Manager.philosophy`. **Voice casting.** Each commentator gets a `VoiceCasting` consistent with persona, gender and age (12 §7); `bindings` stay empty until the TTS phase. 

### 3.3 Stadium, finances, board, fanbase, facilities, staff

- **Stadium & fanbase** by archetype, with a population/fanbase correlation, `passion`/`toxicity`/`fickleness` drawn from archetype ranges (Grafters: high passion, high toxicity; Giants: large, fickle).
- **Finances:** from reputation, attendance potential and broadcast share compute annual income by stream; set `wage_budget_weekly` ≈ 55–65% of income/52 (Boom & Bust: 95%), `transfer_budget` by archetype, `debt` for Old Money (small) and Boom & Bust (large); the opening ledger entry sets `balance`. All Money fields integers.
- **Board:** expectations derived from archetype (title / top-3 / mid-table / avoid relegation / break even), ambition/patience drawn by archetype.
- **Facilities & academy:** levels by archetype (Academy: youth 85–95; Giants: training 85+).
- **Staff:** per club 1 assistant manager, 2 coaches (incl. GK coach), 1 fitness coach, 1–2 physios, 2 scouts, 1 analyst (~8 staff); quality correlated with club money; distinct names; mixed gender.

### 3.4 Referees (10) and Commentators/Media (10)

- **Referees:** 10 officials with spread of `strictness`, `consistency`, `home_bias` (mean +0.1, one outlier +0.4 and one −0.1), `card_tendency`, `added_time_generosity`; a couple of "famous" characters (card-happy; the "lenient old hand"). Names from the neutral culture pool; mixed gender.
- **Media pool:** 2 play-by-play, 2 colour analysts, 2 pitch-side reporters, 2 studio presenters, 3 pundits (= 11; tune to 10–12). Personalities are **authored archetypes** (`archetypes.yaml → media`) instantiated with generated names so each is distinct: e.g. *"the Old Hand"* (calm, measured, history-rich, dry wit, catchphrase on late drama), *"the Firecracker"* (high enthusiasm, big excitement thresholds low, prone to gaffes), *"the Tactician"* (analytic, technical vocabulary, dislikes long-ball football), *"the Local Hero"* (obvious club bias toward one club), *"the Cynic pundit"* (sarcastic, feuding with *"the Optimist"*), *"the Stats Nerd"*, *"the Warm Presenter"*, *"the Provocateur"*. A **distinctness constraint** rejects/re-rolls an instance whose trait vector is within distance ε of another's. Pairings are scripted: 2 duos with high chemistry and running jokes, 1 feud (with `feud_topic`), 1 mentor/mentee pair, club affinities seeded (the Local Hero loves club X, quietly dislikes club Y), a favourite and a disliked player each. `voice`: provider-agnostic voice descriptions with gender/pitch/pace/accent/timbre consistent with the persona and a placeholder `voice_id` (`"voice_placeholder_07"`), unique per person.
- `catchphrases` are authored per archetype with trigger tags that exist in the event vocabulary (validated at load: every tag must be a known `ContextTag`/`EventType`).

### 3.5 Relationships (seed graph)

Per club: 2–4 friendship clusters (shared nationality/age/position group), ~2 mentor→prospect pairs (veteran captain, a youth prospect), 0–2 rival pairs (youth-academy history), 0–1 family pairs league-wide (brothers; father-son coach/player). Manager ↔ key players trust values; manager ↔ board; manager ↔ rival manager (the managers of derby pairs: a spiky rivalry). Media ↔ media as above; media ↔ clubs/players via `biases`. ~600 relationships total; every endpoint exists; no self-links; symmetric kinds canonicalised.

### 3.6 World-systems seed data (revision 2)

- **Staggered contracts:** contract end years are distributed so ≈ 25–30% of each senior squad expires each year (no club has everyone expiring in one summer); a few key players have expiring deals as drama.
- **Free-agent pool:** ~30 unattached players across positions (CA 35–60, ages 20–36) so the first window can always fill gaps; regenerated/topped up each off-season.
- **OUTSIDE_WORLD market:** the generator can produce a window-sized supply (~40 players per window, CA distribution ≈ league mean ± 12, wide age range, foreign nationalities); it is generated on demand from `SimRng(world_seed).fork("outside:<window>")`, not stored in the seed world.
- **Development priors:** `development_rate`, `ability_potential` and `training` plans seeded from archetypes; `development_log` empty; academy prospects carry high PA variance.
- **Initial mood:** ≈ 10% of players start with one mild modifier (e.g. `new_contract_glow`, `homesickness`), so the first matchday already shows variety; `WorldEvent` feed empty except the world-creation event.
- **Calendar:** season 1 starts on a fixed in-world date (default 2031-08-15); transfer windows and contract-end day derive from `LeagueCalendarConfig`.

## 4. Name generation: diverse, plausible, entirely invented

`data/static/name_cultures.yaml` defines **~14 invented cultures**: 6 regional cultures within Valmere (e.g. highland/clipped, coastal/vowel-rich, river-valley/compound surnames, port-city/mixed, border/hyphenated, island/patronymic-ish) and 8 foreign nations (each with its own phoneme inventory). Per culture:

- **Phonology:** onsets, nuclei, codas (weighted), forbidden clusters, allowed word-initial/final consonants, stress rules, syllable-count distributions.
- **Structure:** given-name grammar (1–3 syllables, optional suffix list), surname grammar (root + suffix e.g. `-son/-ek/-ari/-vane`, compounds `X+Y`, patronymic/matronymic forms, particles like `de`/`al`/`van` as fictional particles `ve`, `ar`, `tho`), the share of double-barrelled names, optional hyphenation.
- **Orthography:** simple romanisation with ≤ 2 diacritic types per culture, no real-world flags.
- Phonetic output: the same grammar emits `Pronunciation{respelling, ipa, stress_syllable}` for the future TTS layer.

**Quality gates (applied to every generated name):** length 3–14 per component; no triple letters; vowel/consonant ratio window (pronounceability); no profanity/slur substrings (curated blocklist); **real-world collision filter** — a deny-list of ~1,000 famous real footballer/manager/commentator surnames *and* real club names, plus any exact full-name match is rejected (the grammars are synthetic, but the filter is a safety net; the deny-list lives in `data/static/denylist.txt` and the test asserts none appear); uniqueness (`known_as` unique world-wide; a surname may repeat ≤ 2 times and only for family pairs or common-surname tokens); each culture's names should look *different* from one another (a statistical test: character n-gram distance between cultures exceeds a threshold). **Diversity quota per club:** at least 4 nationalities in the senior squad, no nation > 55%.

## 5. Coherence checks (`seed --validate`, also test-suite)

1. Every FK resolves (clubs ↔ players ↔ contracts ↔ squad entries ↔ staff ↔ relationships).
2. Squad sizes, positional coverage, formation coverage, GK bench rule, shirt number uniqueness per club (1–99), exactly one captain candidate.
3. Wage bill within 85–105% of budget (Boom & Bust exempt but ≤ 125%); club balance + debt consistent with opening ledger; all Money ints.
4. Team ratings follow the archetype bands; best–worst gap within [18, 26]; no two adjacent clubs closer than 0.5.
5. Age/height/weight/ability ranges; `potential ≥ current`; competence rules (GK vs outfield).
6. Names: uniqueness, denylist, culture quotas; pronunciations present.
7. Media: distinctness, all catchphrase tags valid, each role filled, voice ids unique, relationships consistent.
8. Referees: at least one lenient/strict/card-happy; home_bias distribution.
9. Schedule: valid double round robin (each pair twice, once home/once away), no club twice in a matchday, ≤ 2 consecutive home/away, derbies not on matchday 1, balanced slot allocation.
10. Determinism: regenerating from the same seed yields identical `content_sha256`.
11. Everything validates against Pydantic models and exports to the committed JSON Schemas.

## 6. Why a generator and not hand-written data

Hand-authoring 264 players with coherent attributes is neither reproducible nor tunable; the generator makes world shape a *parameter* (strength spread, money, ageing), lets the balance harness vary it, and gives the user "regenerate the world" as a first-class action. Hand-authored content is limited to what benefits from authorship: archetype definitions, role/trait/injury tables, name-culture grammars, media personalities and their catchphrases, and the archetype assignment of the eight clubs. Generated worlds can be edited by hand afterwards (they are plain JSON) — the loader re-validates.

## 7. As built (M2)

What the implementation does differently from the plan above (full list in `docs/milestones/M2.md`):

- `contracts.json` is not written: contracts are embedded in the player, manager and staff rows. `seasons.json` holds the first season without fixtures; the schedule and its coherence check (section 5 item 9) arrive with the league layer (M9).
- Randomness uses `domain.rng.WorldRng` (same interface as `SimRng`) with the sub-streams named in section 1. Ids come from `domain.ids.IdMint`.
- Senior squads draw 10-13 Valmerians and the rest from 3-5 foreign nations so no nation exceeds 55%; the 70/30 split applies to youth and free agents.
- The coherence checks live in `verify/world*.py` (codes W01-W03, W07-W10 and C01-C08), not in `seed/`, because the invariant catalogue is single-sourced there.
- Players are built as `level + shape`: shape is position bias + archetype bias + three correlated latent factors + noise, and the integer level is solved against `domain.ratings.ability_from_attributes`, so generated ability equals the target within 1.
- Clubs are calibrated by retrying the squad with a corrected quality until the best XI's `team_rating` is within 0.6 of the archetype target; a discarded attempt is rolled back (names, ids) with checkpoints.
