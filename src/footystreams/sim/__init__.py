"""The pure match simulation: simulate_match(setup, seed, config) -> events.

May import: domain, events. No I/O, no wall clock, no global randomness, no libm-dependent maths,
no numpy. Randomness only through the SimRng instance passed in.
Design: docs/design/02-simulation.md.
"""
