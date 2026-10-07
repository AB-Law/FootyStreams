---
paths:
  - "src/footystreams/**/*.py"
---
# Architecture rules

Imports point **down**: `domain` <- `events` <- `sim` <- `league` <- (`persistence` ports) <- `runtime`/`cli`.
- `domain` imports nothing from the project. `events` -> `domain`. `sim` -> `events`, `domain`. `league` -> `sim`, `events`, `domain`, persistence **ports** (never SQLAlchemy). `persistence` -> `domain`, `events`. `extensions` -> `domain`, `events` only. `verify` -> `domain`, `events`.
- `runtime/` (the long-running engine, `uv run engine`) is the only package that may use the wall clock, asyncio, signals and lock files. `cli/` and `runtime/main.py` are composition roots: wire concrete implementations there and nowhere else.
- The CLIs are thin wrappers over library functions; never put logic in `cli/`.
- Seams: pure `simulate_match`; sim component Protocols; repository ports (`WorldReader`, per-entity repositories, `UnitOfWork`); `Narrator`, `MemoryUpdater`, `VoiceSynthesizer`, `EventSink`, `ManagerPolicy`. Each is documented at the top of its module.
- Ground truth (attributes, state, results, events, finances) is written only by deterministic code. LLM-origin content may only arrive as validated, bounded **proposals** applied between matches (`docs/design/04-architecture.md` 4.4). Match snapshots (`PlayerSnapshot`, `TeamSheet`) are frozen copies; the sim never reads a database.
- Behaviour that varies lives in data or a registry: tactic modules, roles, traits, formations, mood kinds, balance profiles, event types.
- Persistence: relational columns for everything queried/sorted; validated JSON document for nested structure; `rev` for optimistic concurrency; one transaction per match and per daily-tick stage; stages are idempotent.
