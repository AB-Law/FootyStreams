"""Pitch geometry: metres, attack-normalised frames and point/segment distances.

Positions are stored as absolute normalised coordinates (x along the pitch, y across it, both in
[0, 1], home attacks +x in the first half). Decisions are made in a team's own *frame*, where x = 0
is the team's own goal line and x = 1 the opponent's: `frame_coordinate` flips an absolute value
into the frame and back (it is its own inverse). Only exact operations and `sqrt` are used.
"""

from __future__ import annotations

from math import sqrt

Point = tuple[float, float]

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
GOAL_WIDTH_M = 7.32
CENTRE = 0.5
PENALTY_AREA_DEPTH = 16.5 / PITCH_LENGTH_M
PENALTY_AREA_HALF_WIDTH = 20.16 / PITCH_WIDTH_M


def frame_coordinate(value: float, attack_dir: int) -> float:
    """Map an absolute x or y into a team's frame (and back): identity when attacking +x."""
    return value if attack_dir > 0 else 1.0 - value


def distance_m(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the distance in metres between two normalised points."""
    dx = (x2 - x1) * PITCH_LENGTH_M
    dy = (y2 - y1) * PITCH_WIDTH_M
    return sqrt(dx * dx + dy * dy)


def squared_distance_m(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the squared distance in metres squared (cheaper when only ordering matters)."""
    dx = (x2 - x1) * PITCH_LENGTH_M
    dy = (y2 - y1) * PITCH_WIDTH_M
    return dx * dx + dy * dy


def goal_distance_m(frame_x: float, frame_y: float) -> float:
    """Return the distance from a frame point to the centre of the goal it attacks."""
    return distance_m(frame_x, frame_y, 1.0, CENTRE)


def segment_distance_m(point: Point, start: Point, end: Point) -> float:
    """Return the distance in metres from `point` to the segment `start`-`end` (all normalised)."""
    abx = (end[0] - start[0]) * PITCH_LENGTH_M
    aby = (end[1] - start[1]) * PITCH_WIDTH_M
    apx = (point[0] - start[0]) * PITCH_LENGTH_M
    apy = (point[1] - start[1]) * PITCH_WIDTH_M
    length_squared = abx * abx + aby * aby
    if length_squared == 0.0:
        return sqrt(apx * apx + apy * apy)
    along = max(0.0, min(1.0, (apx * abx + apy * aby) / length_squared))
    dx = apx - along * abx
    dy = apy - along * aby
    return sqrt(dx * dx + dy * dy)


def closest_point_on_segment(point: Point, start: Point, end: Point) -> Point:
    """Return the point of the segment `start`-`end` nearest to `point` (all normalised)."""
    abx = (end[0] - start[0]) * PITCH_LENGTH_M
    aby = (end[1] - start[1]) * PITCH_WIDTH_M
    length_squared = abx * abx + aby * aby
    if length_squared == 0.0:
        return start
    apx = (point[0] - start[0]) * PITCH_LENGTH_M
    apy = (point[1] - start[1]) * PITCH_WIDTH_M
    along = max(0.0, min(1.0, (apx * abx + apy * aby) / length_squared))
    return start[0] + along * (end[0] - start[0]), start[1] + along * (end[1] - start[1])


def in_penalty_area(frame_x: float, frame_y: float) -> bool:
    """True when a frame point lies inside the penalty area the team attacks."""
    return frame_x >= 1.0 - PENALTY_AREA_DEPTH and abs(frame_y - CENTRE) <= PENALTY_AREA_HALF_WIDTH


def centrality(frame_y: float) -> float:
    """Return 1 on the centre line falling linearly to 0 at either touchline."""
    return 1.0 - 2.0 * abs(frame_y - CENTRE)
