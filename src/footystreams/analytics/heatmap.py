"""Heatmaps: where a player or a team spent the match, from tracking frames or touches."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.types import PlayerId
from footystreams.events.derive.threat import GRID_COLUMNS, GRID_ROWS
from footystreams.events.structure import FrameEvent
from footystreams.events.types import MatchEvent

HeatGrid = tuple[tuple[int, ...], ...]  # GRID_ROWS rows of GRID_COLUMNS counts, absolute pitch


def _cell(x: float, y: float) -> tuple[int, int]:
    column = min(GRID_COLUMNS - 1, max(0, int(x * GRID_COLUMNS)))
    row = min(GRID_ROWS - 1, max(0, int(y * GRID_ROWS)))
    return row, column


def _grid(cells: Sequence[tuple[int, int]]) -> HeatGrid:
    counts = [[0] * GRID_COLUMNS for _ in range(GRID_ROWS)]
    for row, column in cells:
        counts[row][column] += 1
    return tuple(tuple(line) for line in counts)


def frame_heatmap(events: Sequence[MatchEvent], player_ids: frozenset[PlayerId]) -> HeatGrid:
    """Count, per grid cell, the frames in which any of `player_ids` stood there."""
    cells = [
        _cell(player.x, player.y)
        for event in events
        if isinstance(event, FrameEvent)
        for player in event.players
        if player.player_id in player_ids
    ]
    return _grid(cells)


def touch_heatmap(events: Sequence[MatchEvent], player_id: PlayerId) -> HeatGrid:
    """Count, per grid cell, the events a player took part in (works without frames)."""
    cells = [
        _cell(event.pos.x, event.pos.y)
        for event in events
        if event.pos is not None
        and any(participant.player_id == player_id for participant in event.participants)
    ]
    return _grid(cells)
