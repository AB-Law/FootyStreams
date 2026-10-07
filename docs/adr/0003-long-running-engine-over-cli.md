# ADR 0003: The product is a long-running engine; the CLIs are thin tools

Status: accepted (2026-10-07). Design reference: `docs/design/13-runtime-engine.md`.

## Context
The league is meant to run as a 24/7 broadcast. A command that runs, prints and exits is the wrong shape for
that. The original brief also asked for `sim`, `league` and `seed` commands.

## Decision
- The primary executable is `uv run engine`: a supervised, crash-only service that simulates ahead of airtime,
  verifies every match, replays verified logs at broadcast pace, and publishes to pluggable sinks.
- `sim`, `seed`, `league`, `verify`, `health` and the other commands stay as thin developer and operator tools
  that call the same library code; they hold no logic of their own.
- Only the `runtime` package may use the wall clock, asyncio, signals and lock files.

## Consequences
- Resilience features (playback cursor, idempotent stages, quarantine and fallback) are first-class.
- Tests can drive the engine with a virtual clock and run a season in seconds.
- The layering rule (`runtime` and `cli` are composition roots) is enforced by the architecture checker.
