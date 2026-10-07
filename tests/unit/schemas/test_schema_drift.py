"""Committed schemas/ must match a fresh export (LF, canonical JSON)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from footystreams.cli.export_schemas import export_all
from footystreams.tools.paths import PROJECT_ROOT

SCHEMAS = PROJECT_ROOT / "schemas"


def test_schemas__match_fresh_export() -> None:
    assert SCHEMAS.is_dir(), "schemas/ missing; run: uv run export-schemas"
    with tempfile.TemporaryDirectory() as tmp:
        export_all(Path(tmp))
        committed = {
            path.relative_to(SCHEMAS): path.read_bytes()
            for path in SCHEMAS.rglob("*")
            if path.is_file()
        }
        fresh = {
            path.relative_to(Path(tmp)): path.read_bytes()
            for path in Path(tmp).rglob("*")
            if path.is_file()
        }
    assert committed.keys() == fresh.keys()
    mismatches = [str(rel) for rel in sorted(committed) if committed[rel] != fresh[rel]]
    assert not mismatches, "schema drift in: " + ", ".join(mismatches)
