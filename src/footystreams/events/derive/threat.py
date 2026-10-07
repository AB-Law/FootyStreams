"""The threat surface and the pitch grid, shared by the simulator and the analytics.

`threat` is how dangerous it is to hold the ball at a point, a smooth analytic function of the
attacking frame (x toward the goal being attacked, y across), so the gain of a pass is the
difference of two evaluations (docs/design/02 section 5.2). `zone_of` bins a frame point into the
12 x 8 grid used by the summary's pass-flow map.
"""

from __future__ import annotations

THREAT_PEAK = 0.13
WIDE_FLOOR = 0.35  # a wide position keeps this share of a central position's threat
GRID_COLUMNS = 12  # along the pitch
GRID_ROWS = 8  # across the pitch
_CENTRE = 0.5


def frame_value(value: float, attack_dir: int) -> float:
    """Map an absolute x or y into the attacking team's frame (identity when attacking +x)."""
    return value if attack_dir > 0 else 1.0 - value


def centrality(frame_y: float) -> float:
    """Return 1 on the centre line falling linearly to 0 at either touchline."""
    return 1.0 - 2.0 * abs(frame_y - _CENTRE)


def threat(frame_x: float, frame_y: float) -> float:
    """Return the danger of the ball at a frame point: 0.13 * x^4 * (0.35 + 0.65 * centrality)."""
    square = frame_x * frame_x
    return THREAT_PEAK * square * square * (WIDE_FLOOR + (1.0 - WIDE_FLOOR) * centrality(frame_y))


def zone_of(frame_x: float, frame_y: float) -> int:
    """Return the grid zone (0-95, column-major) of a frame point; edges fold inward."""
    column = min(GRID_COLUMNS - 1, max(0, int(frame_x * GRID_COLUMNS)))
    row = min(GRID_ROWS - 1, max(0, int(frame_y * GRID_ROWS)))
    return column * GRID_ROWS + row
