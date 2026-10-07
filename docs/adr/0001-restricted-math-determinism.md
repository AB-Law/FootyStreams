# ADR 0001: Restrict the simulation to exact arithmetic and our own RNG

Status: accepted (2026-10-07). Design reference: `docs/design/02-simulation.md` section 1 and 13.

## Context
The same seed and inputs must give a byte-identical event log, on Windows and Linux, across Python
patch versions. Golden digests, replays, crash recovery, the pre-air verification gate and future
learning managers all depend on this. Floating-point functions backed by the platform's C maths
library (`exp`, `log`, `sin`, ...) and library-level random distributions (numpy, `random.gauss`)
may differ in the last digit between platforms or versions, which changes a comparison somewhere and
then the whole match.

## Decision
- Inside `src/footystreams/sim/` use only IEEE-exact operations: `+ - * /`, `sqrt` and comparisons.
- Use our own `SimRng` (Mersenne Twister `random()` stream with named, isolated sub-streams) and our own
  algebraic helpers (`squash`, `gauss` as a sum of uniforms) instead of library distributions.
- No numpy, wall clock, `hash()`, `id()` or set iteration in the simulation.
- Enforced mechanically by `footystreams.tools.architecture` (rules in `rules.py`) and its canary tests.

## Consequences
- Slightly unusual maths (algebraic sigmoids, approximate normals) and a custom RNG wrapper.
- Contributors cannot reach for numpy or `math.exp` in `sim/`; the architecture test explains why.
- Cross-platform golden digests become meaningful and CI can verify them on both operating systems.
- Known limit: the checker matches names, so `import math as m` would not be caught; review covers that.
