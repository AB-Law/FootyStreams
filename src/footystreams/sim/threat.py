"""The threat surface: how dangerous it is to hold the ball at a point.

A smooth analytic function of the attacking frame, so the gain of a pass or dribble is just the
difference between two evaluations (docs/design/02 section 5.2). Calibrated so that the six-yard
box is worth about 0.10 and the own penalty area almost nothing.
"""

from __future__ import annotations

from footystreams.sim.geometry import centrality

THREAT_PEAK = 0.13
WIDE_FLOOR = 0.35  # a wide position keeps this share of a central position's threat


def threat(frame_x: float, frame_y: float) -> float:
    """Return the danger of the ball at a frame point: 0.13 * x^4 * (0.35 + 0.65 * centrality)."""
    square = frame_x * frame_x
    return THREAT_PEAK * square * square * (WIDE_FLOOR + (1.0 - WIDE_FLOOR) * centrality(frame_y))
