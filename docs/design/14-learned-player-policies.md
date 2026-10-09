# 14 — Learned player policies and compute (exploratory notes)

**Status: EXPLORATORY. Nothing here is decided or built.** These are notes from a design discussion (2026-10-09), kept so the thinking is not lost. They extend 08 §1 ("player-specific behaviour") and 08 §2 (learning managers) from managers down to individual players. Measured numbers are marked *measured*; everything else is an estimate or an opinion.

## 1. What prompted it

The sim should give each player more of a "thought process": more events that show why a player did something (a run in behind, a check to the ball, a press trigger, an overlap), and players who are visibly smarter or dimmer. The question was whether to train neural networks for this, possibly one per quality level (relegation midfielder, mid-table, elite...).

## 2. Ideas and where the discussion landed

1. **Per-player decision seam.** Every player's choice (carrier: pass / dribble / shoot / hold; off the ball: run, support, press, cover) goes through one interface that returns the choice and a **reason code**. Today's rule-based scorer (`sim/decision.py`, `sim/options.py`, `sim/positioning.py`) is the baseline implementation. Off-ball intents become events at full verbosity (commentary and the viewer can use them). This is useful with or without any learning, and is the seam a learned policy would plug into. It mirrors `ManagerPolicy` (08 §2): `policy_id` and `policy_version` recorded on the match, snapshots content-addressed, so a match with a learned policy stays exactly replayable.
2. **Quality is per player, not per club or per model.** An elite midfielder and a mid-table midfielder are different **rating profiles**, not different networks. One policy takes the player's ratings (vision, passing, decisions, composure, pace, stamina...) as inputs, so a champion-level brain with poor physicals plays around his physicals. This avoids cliff effects when a player develops or changes club. "A team signs a mid-mid instead of an elite mid" is already modelled on the league side: `league/scouting.py` gives clubs a noisy estimate of a player that sharpens with their judging. The match model only has to respond honestly to the true ratings.
3. **Levels as dials**, usable with the rule-based scorer today: how many options a player notices (vision), how sharp his choice is versus sometimes taking the second best, how early he reads a pass, how fast he reacts. Tune against the balance harness.
4. **Learning from scratch with the rules.** Legitimate: the sim is the environment, reward is winning (with shaped intermediate rewards), no real data needed. Tracking data is optional (at most a warm start by imitation; check dataset licences first). Realism is not required; sensible, varied, quality-sensitive football is.
5. **Players training against each other** (league / population self-play: play older versions of themselves to avoid cycling between counter-strategies). A second phase, after one policy works.

## 3. Constraints any learned policy must respect

- **Determinism.** Same seed, byte-identical event log. Training can be nondeterministic; the **shipped** forward pass must not be: weights are versioned data, fixed operation order, float64 on CPU, `SIM_VERSION` bump on every retrain. No BLAS-order surprises (avoid numpy matmul for tiny nets).
- **Rules stay in the rules.** The network only **ranks options the rules already allow**. It cannot invent an illegal action, and `verify/` invariants still apply.
- **The sim is the teacher, so its quirks are learnable exploits.** Guard rails: the balance bands (goals, shots, pass completion, 33 of 43 metrics currently pass) are asserted per policy, as 08 §2 already requires for managers.
- **Explainability.** Commentary needs a reason ("found the free man on the left"). A policy must return a reason code, not only a score.
- **Cost.** See §4: a small network on the carrier's decision is affordable; per-player off-ball inference is not, in Python.

## 4. Compute (what is measured and what is not)

*Measured on 2026-10-09, Ryzen 5 7600 (6 cores / 12 threads), RTX 4070 Ti SUPER 16 GB, Windows, Python sim:*

| Fact | Value |
|------|-------|
| One match, pure sim CPU (demo teams, no frames or with 1 Hz frames) | about 0.42 s (design budget 150 ms, never met) |
| Decision ticks / events per match | about 1,270 / about 1,500 |
| Profile split (cProfile, one match) | off-ball positioning about 46%, decisions and option generation about 24%, pass resolution about 15%, event emit and validation about 12% |
| Serialising a match's events to JSON | about 16 ms |
| CLI run of one match end to end | about 1.7 s, mostly startup and YAML world loading |
| PR-tier quality gate | about 550 s, mostly sim-heavy tests under coverage |
| Live broadcast CPU | 0.42 s per 95 match-minutes, about 0.007% of one core: the live engine is not CPU-bound |

*Estimates (not measured):*

| Option | Throughput estimate | Notes |
|--------|---------------------|-------|
| Python sim, carrier-choice policy only | 100 million decisions is about 80,000 matches, about 9 CPU-hours (about 1 to 2 h on 10 workers) | Enough for a first experiment. A small MLP in pure Python adds roughly 0.1 s per match. |
| Python sim, all 22 players learning off-ball | about 20x more steps | Too slow in Python. |
| Rust sim on CPU (PyO3), hot loop only | 8 to 15x faster (about 30 to 50 ms per match) | Events still handed to Python. Positioning alone gives only about 1.8x overall. |
| Rust sim on CPU, everything | 40x or more (about 10 ms per match) | About 15,000 lines (`sim/`, `events/`, `domain/`); tests are in Python and need a binding. Float maths (sin, cos, exp) can differ from Python's in the last bit, so goldens change: `SIM_VERSION` bump, regenerate, recalibrate. With 12 threads: roughly 600 to 1,000 matches a second, so the carrier experiment in about 2 minutes and all-22 off-ball learning in about 30 to 40 minutes. |
| Sim as a GPU environment (Isaac Gym / Brax style) | 10,000+ matches in lockstep | A ground-up rewrite to flat arrays and fixed-size records. A second copy of the rules that can drift from the shipped sim, and not bit-reproducible across GPUs, so training-only. Only worth it beyond about 10 billion decisions. |
| GPU for the learner only (PyTorch) | helps the gradient updates | The bottleneck is the sim on CPU, not the network. Small nets can even be slower on GPU. Fine as the learner; not a speed-up of the matches. |

Where the speed matters: batch work (balance runs, 1,200-match statistical tier, 20-season runs, the test gate) and any training. It does not matter for the live stream.

## 5. Suggested order (opinion, to revisit)

1. **Decision seam and off-ball intent events**, with reason codes. Useful on its own.
2. **Level dials** driven by ratings, tuned with the balance harness.
3. **Throwaway experiment:** learn only the carrier's choice from scratch on the current Python sim (PyTorch on the GPU as the learner, CPU workers playing matches). Look at what behaviour appears before committing to more. Judge a policy by whether it beats the baseline over many matches while the balance bands hold.
4. **Rust on CPU for the hot loop**, only if the experiment earns it or batch speed hurts. Cheaper steps first: optimise the Python hot spots (precomputed distances, fewer per-tick allocations; roughly 2 to 3x, low risk).
5. **Off-ball learning and league self-play** last.
6. A **GPU environment** only if training needs billions of decisions.

## 6. Open questions

- The reward: win, goal difference, xG-based shaping, or a mix? How to keep it from rewarding sim artefacts?
- Which decisions first after the carrier's choice (press trigger, support position, defender jobs)?
- Observation features: which of the quantities already computed (lane openness, pressure, support angles, space) are enough, and how are ratings fed in so the policy generalises across rating profiles (train with widely randomised ratings)?
- How weights ship: file format, content hash, the `SIM_VERSION` / `policy_version` relationship, and what a retrain does to goldens.
- Whether open tracking data is worth a warm start, after checking licences.
- How "dim" players stay dim: dials versus a smaller or noisier policy.
