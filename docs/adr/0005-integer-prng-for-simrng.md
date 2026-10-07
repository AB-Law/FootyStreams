# ADR 0005: SimRng is a self-contained integer PRNG (xoshiro256**)

Status: accepted (2026-10-08, Track A / M4). Refines ADR 0001 and docs/design/02 section 13.

## Context
Design 02 section 13 describes `SimRng` as a wrapper around `random.Random(seed)`. The architecture
rules (`tools/architecture/rules.py`, `IMPURE_MODULES`) forbid importing `random` anywhere in the pure
layers, including `sim/`. Weakening that rule would let global randomness creep in.

## Decision
`sim/rng.py` implements xoshiro256** (state seeded with splitmix64) using Python integers and masks
only. `u()` is `(next_u64() >> 11) * 2**-53`, which is exact. `fork(label)` derives a child seed with
`blake2b(seed:label)`. The class counts its draws so stream-isolation tests can compare counters.

## Consequences
- Identical streams on every platform and Python version, with no dependency on the standard library's
  generator; a known-answer test pins the output.
- Slightly slower than `random.random()` (pure Python, about 1 microsecond per draw); acceptable for the
  budget (about 10k draws per match).
- Design 02 section 13 is updated to describe this generator.
