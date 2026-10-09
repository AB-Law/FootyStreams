"""Realism numbers for a recorded replay, to compare before and after a movement change.

It reads the `frame` events of a replay NDJSON and prints how players actually move between
frames: speed from position change (not the reported speed, which hides teleports), idle share,
how far a ball carrier travels while holding the ball, and how compact each side stays.

    uv run python viewer/scripts/frame_metrics.py viewer/replays/baseline.ndjson
"""

from __future__ import annotations

import argparse
import json
import math
from itertools import pairwise
from pathlib import Path

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
IDLE_MPS = 0.3
TELEPORT_MPS = 12.0


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else 0.0


def _metres(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot((b["x"] - a["x"]) * PITCH_LENGTH_M, (b["y"] - a["y"]) * PITCH_WIDTH_M)


def read_frames(path: Path) -> list[dict[str, object]]:
    """The frame events of a replay, in order."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if '"type":"frame"' in line]


def _team_shape(frame: dict[str, object]) -> tuple[float, float]:
    """Length and width in metres of the outfield players of the first team in the frame."""
    outfield = frame["players"][1:11]  # type: ignore[index]
    xs = [p["x"] * PITCH_LENGTH_M for p in outfield]
    ys = [p["y"] * PITCH_WIDTH_M for p in outfield]
    return max(xs) - min(xs), max(ys) - min(ys)


def compute(frames: list[dict[str, object]]) -> dict[str, float]:
    """Movement statistics over consecutive frames (assumes a constant frame interval)."""
    speeds: list[float] = []
    carrier_run: list[float] = []
    run_total = 0.0
    run_carrier = None
    for before, after in pairwise(frames):
        if before["clock"]["period"] != after["clock"]["period"]:  # type: ignore[index]
            continue  # the break teleports everyone to the kick-off; there is no play to measure
        index = {p["player_id"]: p for p in before["players"]}  # type: ignore[attr-defined]
        for player in after["players"]:  # type: ignore[attr-defined]
            previous = index.get(player["player_id"])
            if previous is not None:
                speeds.append(_metres(previous, player))
        carrier = after["carrier_id"]
        if carrier == run_carrier and carrier in index:
            moved = [p for p in after["players"] if p["player_id"] == carrier]  # type: ignore[attr-defined]
            run_total += _metres(index[carrier], moved[0])
        else:
            if run_carrier is not None:
                carrier_run.append(run_total)
            run_carrier, run_total = carrier, 0.0
    lengths = [_team_shape(frame)[0] for frame in frames]
    widths = [_team_shape(frame)[1] for frame in frames]
    count = max(1, len(speeds))
    return {
        "frames": float(len(frames)),
        "speed_p99_mps": _percentile(speeds, 0.99),
        "speed_max_mps": max(speeds, default=0.0),
        "teleport_share_pct": 100 * sum(s > TELEPORT_MPS for s in speeds) / count,
        "idle_share_pct": 100 * sum(s < IDLE_MPS for s in speeds) / count,
        "carrier_metres_per_hold": sum(carrier_run) / max(1, len(carrier_run)),
        "team_length_m": sum(lengths) / max(1, len(lengths)),
        "team_width_m": sum(widths) / max(1, len(widths)),
    }


def main() -> None:
    """Print the metrics of one replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    arguments = parser.parse_args()
    for name, value in compute(read_frames(arguments.replay)).items():
        print(f"{name:26s} {value:10.2f}")


if __name__ == "__main__":
    main()
