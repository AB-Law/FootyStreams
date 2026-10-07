# FootyStreams

A fictional football league that runs as a 24/7 live broadcast: a deterministic match simulation, a typed event stream, and a living league world (mood, development, contracts, transfers). Commentary, voice and rendering are future layers behind clean extension points.

**Status:** design complete (`docs/design/`), implementation starting (milestone M0). This README is expanded in the final milestone.

## Quick start

```bash
uv sync
uv run check        # ruff, ruff format, mypy --strict, changelog checks, tests
git config core.hooksPath .githooks   # once per clone: runs the gate before each commit and checks commit messages
```

Design index: [`docs/design/README.md`](docs/design/README.md). Agent rules: [`AGENTS.md`](AGENTS.md).
