"""Schema and simulation version constants.

``SCHEMA_VERSION`` bumps when events/models JSON Schema changes.
``SIM_VERSION`` bumps when match output for a fixed seed changes.

Initial ``SCHEMA_VERSION`` is ``0.1.0`` (not ``1.0.0``): design 03 treats field
meaning/shape changes as major, so starting at 1.0.0 would force the first
parallel-track fix to 2.0.0. Promote to 1.0.0 once M2 and M4 have exercised the
contracts. ``SIM_VERSION`` is ``0.3.0`` after M6 (``0.1.0`` was the first simulator, M4;
``0.2.0`` M5); each milestone that changes match output bumps it (goldens:
``uv run golden update``).
"""

from __future__ import annotations

SCHEMA_VERSION = "0.1.5"
SIM_VERSION = "0.3.0"
