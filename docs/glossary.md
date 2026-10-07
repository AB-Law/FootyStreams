# Glossary (ubiquitous language)

One meaning per word, used the same way in code, docs and conversation. Rename project-wide, never locally.

| Term | Meaning |
|------|---------|
| **Attribute** | One skill of one person on a 1-100 scale (finishing, vision, pace). A player has about 50 of them. |
| **Competence** | 0-100 suitability for a position, role or formation; scales attributes, is not a skill. |
| **Snapshot** | A frozen copy of an entity for one match (`PlayerSnapshot`). The simulation never reads a database. |
| **Sheet** (`TeamSheet`) | Everything one side brings to a match: lineup, bench, tactics, manager, snapshots. |
| **Setup** (`MatchSetup`) | The complete simulation input: two sheets, referee, weather, attendance, rules. |
| **Moment** | One resolved on-ball action or restart inside the simulation. |
| **Chain** | A possession sequence; its id changes on every change of possession. |
| **Phase** | Where play is: build-up, progression, final third, transition, set piece, dead ball. |
| **Slot** | One of the 11 positions of a formation, numbered 0-10. |
| **Role** / **duty** | A behaviour template (e.g. winger, anchor) and its emphasis (defend, support, attack). |
| **Tactics** | A versioned core plus tactic modules (pressing, build-up, ...); read by the simulation through a view. |
| **Line** | A row of players (defensive line) or its position on the pitch. |
| **Press** | Coordinated pressure on the ball carrier; intensity and triggers are tactics settings. |
| **Event** | One entry of the match log, a member of the discriminated event union. |
| **Significance** | 0-1 score of how much an event matters; commentary and filtering use it. |
| **Digest** | SHA-256 of the canonical event log; proves two runs are byte-identical. |
| **Seed** | The integer that, with the inputs and config, fully determines a simulation or a world. |
| **Stream** | A named, isolated sub-sequence of the RNG (play, discipline, injury, ...). |
| **Profile** (model) | The selected set of simulation components (`model_profile`). |
| **Profile** (balance) | A named set of balance targets (realistic, chaos, ...). |
| **Knob** | A named, documented tunable in `SimConfig` or a YAML file. |
| **Matchday** | A round of fixtures; weekly in world time. |
| **Window** | A transfer window. |
| **Ledger** | The append-only list of money movements for a club; balance is derived from it. |
| **Mood** / **modifier** | A time-limited life episode (`StateModifier`) resolved into capped performance multipliers before a match. |
| **Storyline** | A public fact attached to a person or match that commentary may mention. |
| **Verify** | The single invariant catalogue (`footystreams.verify`) used by tests and the pre-air gate. |
| **Quarantine** | Status of a match that failed verification and is never aired. |
| **Engine** | The long-running service (`uv run engine`) that keeps the broadcast going. |
| **Fragment** | A change-log entry file in `changes/`. |
| **Gate** | `uv run check`, the quality gate every change and agent turn must pass. |
| **Tier** | How much of the gate runs: fast (every commit/turn), pr, nightly, release. |
| **Canary** (test) | A test that feeds a deliberately bad input to prove a rule can still fail. |
