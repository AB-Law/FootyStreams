"""The threat surface: how dangerous it is to hold the ball at a point.

The formula lives in `events/derive/threat.py` so the analytics that recompute pass maps from the
log use exactly the surface the decision model played with. Calibrated so that the six-yard box
is worth about 0.10 and the own penalty area almost nothing (docs/design/02 section 5.2).
"""

from __future__ import annotations

from footystreams.events.derive.threat import THREAT_PEAK, WIDE_FLOOR, threat

__all__ = ["THREAT_PEAK", "WIDE_FLOOR", "threat"]
