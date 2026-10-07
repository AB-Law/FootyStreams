"""Committed schemas/*.schema.json must match a fresh export (LF, canonical JSON).

``schemas/CHANGELOG.md`` is hand-maintained and excluded from the byte comparison.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from footystreams.cli.export_schemas import export_all
from footystreams.tools.paths import PROJECT_ROOT

SCHEMAS = PROJECT_ROOT / "schemas"


def _schema_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*.schema.json")
        if path.is_file()
    }


def test_schemas__match_fresh_export() -> None:
    assert SCHEMAS.is_dir(), "schemas/ missing; run: uv run export-schemas"
    with tempfile.TemporaryDirectory() as tmp:
        export_all(Path(tmp))
        committed = _schema_files(SCHEMAS)
        fresh = _schema_files(Path(tmp))
    assert committed.keys() == fresh.keys()
    mismatches = [str(rel) for rel in sorted(committed) if committed[rel] != fresh[rel]]
    assert not mismatches, "schema drift in: " + ", ".join(mismatches)
