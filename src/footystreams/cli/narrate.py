"""``uv run narrate``: pack match facts and write a studio commentary script (LLM or template)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from footystreams.cli.lm_client import DEFAULT_ENDPOINT, DEFAULT_MODEL
from footystreams.cli.lmstudio_narrator import LMStudioNarrator
from footystreams.cli.sim_world import resolve_world_match
from footystreams.extensions.brief import CommentaryLine
from footystreams.extensions.pack import pack_broadcast_brief
from footystreams.extensions.template_narrator import TemplateNarrator
from footystreams.persistence.ports import NotFoundError
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.world_io import WorldFileError, read_world
from footystreams.sim import SimConfig, run_match
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"
DEFAULT_OUT = PROJECT_ROOT / "viewer" / "replays" / "commentary.json"
EXIT_OK, EXIT_USAGE = 0, 2


def build_parser() -> argparse.ArgumentParser:
    """Define the narrate command line."""
    parser = argparse.ArgumentParser(prog="narrate", description=__doc__)
    parser.add_argument("--home", required=True, help="club id, short code or name")
    parser.add_argument("--away", required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--engine",
        choices=("template", "lmstudio"),
        default="template",
        help="template (default, offline) or lmstudio (LM Studio local server, template fallback)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="model id as shown in LM Studio (default: local-model)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="LM Studio chat completions URL (default: http://127.0.0.1:1234/v1/chat/completions)",
    )
    parser.add_argument(
        "--brief-out",
        type=Path,
        default=None,
        help="optional path to write the packed BroadcastBrief JSON",
    )
    return parser


def _write_script(path: Path, lines: tuple[CommentaryLine, ...], brief_match_id: str) -> None:
    payload = {
        "match_id": brief_match_id,
        "lines": [line.model_dump(mode="json") for line in lines],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run(arguments: argparse.Namespace) -> int:
    world = read_world(arguments.world)
    found = resolve_world_match(arguments)
    result = run_match(found.setup, arguments.seed, SimConfig(), found.tables, found.referee)
    brief = pack_broadcast_brief(world, found.setup, result.summary)
    if arguments.brief_out is not None:
        arguments.brief_out.parent.mkdir(parents=True, exist_ok=True)
        arguments.brief_out.write_text(brief.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if arguments.engine == "lmstudio":
        narrator: TemplateNarrator | LMStudioNarrator = LMStudioNarrator(
            model=arguments.model, endpoint=arguments.endpoint
        )
    else:
        narrator = TemplateNarrator()
    lines = narrator.narrate(brief, brief.crew)
    _write_script(arguments.out, lines, brief.match_id)
    print(f"wrote {arguments.out} ({len(lines)} lines, engine={arguments.engine})")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry; returns a process exit code."""
    arguments = build_parser().parse_args(argv)
    try:
        return _run(arguments)
    except (ValueError, WorldFileError, StaticDataError, NotFoundError, OSError) as error:
        print(f"narrate: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
