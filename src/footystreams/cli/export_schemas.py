"""Export Pydantic models to committed JSON Schema under schemas/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import TypeAdapter

from footystreams.domain.canonical import canonical_json
from footystreams.domain.registry import DOMAIN_MODELS
from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.events.result import MatchResult
from footystreams.events.summary import MatchSummary
from footystreams.events.types import MatchEvent
from footystreams.tools.paths import PROJECT_ROOT

SCHEMAS_DIR = PROJECT_ROOT / "schemas"
MODELS_DIR = SCHEMAS_DIR / "models"


def export_all(root: Path = SCHEMAS_DIR) -> list[Path]:
    """Write event, summary and domain model schemas; return written paths."""
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    events_path = root / "events.schema.json"
    _write_schema(events_path, TypeAdapter(MatchEvent).json_schema())
    written.append(events_path)

    summary_path = root / "match_summary.schema.json"
    _write_schema(summary_path, MatchSummary.model_json_schema())
    written.append(summary_path)

    result_path = root / "match_result.schema.json"
    _write_schema(result_path, MatchResult.model_json_schema())
    written.append(result_path)

    for model in DOMAIN_MODELS:
        path = models_dir / f"{model.__name__}.schema.json"
        _write_schema(path, model.model_json_schema())
        written.append(path)

    return written


def _write_schema(path: Path, schema: object) -> None:
    path.write_text(canonical_json(schema) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry: write schemas/ from the current models."""
    parser = argparse.ArgumentParser(description="Export JSON Schema from Pydantic models")
    parser.add_argument(
        "--out",
        type=Path,
        default=SCHEMAS_DIR,
        help="output directory (default: schemas/)",
    )
    arguments = parser.parse_args(argv)
    paths = export_all(arguments.out)
    print(f"wrote {len(paths)} files under {arguments.out} (SCHEMA_VERSION={SCHEMA_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
