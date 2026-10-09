"""Schema and simulation version constants.

``SCHEMA_VERSION`` bumps when events/models JSON Schema changes.
``SIM_VERSION`` bumps when match output for a fixed seed changes.

Initial ``SCHEMA_VERSION`` is ``0.1.0`` (not ``1.0.0``): design 03 treats field
meaning/shape changes as major, so starting at 1.0.0 would force the first
parallel-track fix to 2.0.0. Promote to 1.0.0 once M2 and M4 have exercised the
contracts. ``SIM_VERSION`` is ``0.7.3`` (supporters keep their angle) after ``0.7.2``
(frames carry velocity) after ``0.7.1`` (an intercepted pass is cut out on its lane) after ``0.7.0``
(lane-cutting defence, free defenders with a job,
attacking support angles) after ``0.6.0`` (shot flights, then living movement: pressing, marking,
wander, box play) after ``0.5.0`` (M8 calibration), ``0.4.1`` (the Track B rebase onto M7;
``0.4.0`` was M7, ``0.1.0`` M4, ``0.2.0`` M5, ``0.3.0`` M6); each change that alters match
output bumps it (goldens: ``uv run golden update``).
"""

from __future__ import annotations

SCHEMA_VERSION = "0.5.1"
SIM_VERSION = "0.7.3"
