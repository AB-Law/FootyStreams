"""The long-running engine (uv run engine): supervisor, simulation buffer, paced playback, sinks.

The only package allowed to use the wall clock, asyncio, signals and lock files.
Design: docs/design/13-runtime-engine.md.
"""
