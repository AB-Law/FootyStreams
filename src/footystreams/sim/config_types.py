"""Bounded number types shared by the SimConfig groups.

Every numeric knob uses one of these (or an explicit `Field` bound), so `merge_config` cannot
build a configuration the simulator would divide by zero on or turn into a negative duration.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

Share = Annotated[float, Field(ge=0.0, le=1.0)]  # a probability or a fraction of something
Positive = Annotated[float, Field(gt=0.0)]
NonNegative = Annotated[float, Field(ge=0.0)]
