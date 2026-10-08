"""``EngineConfig``: every setting of the running engine, frozen and validated.

Pacing is ``realtime`` (one channel second per wall second), ``scaled:N`` (N times faster) or
``instant`` (no waiting; a season in seconds). The block durations are placeholders the
commentary and studio layers will replace; they are deterministic so a rerun lays out the same
programme.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from footystreams.runtime.clock import Clock, ScaledClock, SystemClock, VirtualClock

SCALED_PREFIX = "scaled:"
SECONDS_PER_DAY = 86_400
DEFAULT_DAYS_PER_CHANNEL_DAY = 7  # "one in-world week is one real day"


class PaceKind(StrEnum):
    """How the channel timeline relates to the wall clock."""

    REALTIME = "realtime"
    SCALED = "scaled"
    INSTANT = "instant"


class Pace(BaseModel):
    """A parsed ``--pace`` value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: PaceKind
    speed: float = Field(gt=0.0, default=1.0)

    def clock(self) -> Clock:
        """The clock that runs this pace."""
        if self.kind is PaceKind.INSTANT:
            return VirtualClock()
        return SystemClock() if self.kind is PaceKind.REALTIME else ScaledClock(self.speed)


def parse_pace(text: str) -> Pace:
    """``realtime``, ``scaled:N`` or ``instant``; anything else is a ``ValueError``."""
    if text == PaceKind.REALTIME:
        return Pace(kind=PaceKind.REALTIME)
    if text == PaceKind.INSTANT:
        return Pace(kind=PaceKind.INSTANT)
    if text.startswith(SCALED_PREFIX):
        try:
            return Pace(kind=PaceKind.SCALED, speed=float(text.removeprefix(SCALED_PREFIX)))
        except ValueError as error:
            msg = f"pace {text!r}: scaled needs a positive number, like scaled:200"
            raise ValueError(msg) from error
    msg = f"pace {text!r} must be realtime, scaled:N or instant"
    raise ValueError(msg)


class Programme(BaseModel):
    """Placeholder durations (channel seconds) of the non-match blocks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pre_match_s: float = Field(ge=0.0, default=120.0)
    half_time_s: float = Field(ge=0.0, default=300.0)
    post_match_s: float = Field(ge=0.0, default=180.0)
    magazine_s: float = Field(ge=0.0, default=300.0)
    filler_s: float = Field(gt=0.0, default=600.0)
    day_s: float = Field(gt=0.0, default=SECONDS_PER_DAY / DEFAULT_DAYS_PER_CHANNEL_DAY)


class EngineConfig(BaseModel):
    """The settings of one engine run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_path: Path
    pace: Pace = Pace(kind=PaceKind.REALTIME)
    buffer_matchdays: int = Field(ge=0, le=10, default=1)
    max_seasons: int | None = Field(ge=1, default=None)
    until_date: dt.date | None = None
    sinks: tuple[str, ...] = ("ndjson:stdout",)
    sink_queue: int = Field(ge=1, default=2000)
    sink_timeout_s: float = Field(gt=0.0, default=5.0)
    cursor_every: int = Field(ge=1, default=25)
    starve_grace_s: float = Field(ge=0.0, default=2.0)  # real seconds to wait for the buffer
    lock_grace_s: float = Field(ge=0.0, default=3.0)  # patience for a crashed holder's lock
    max_lag_s: float = Field(gt=0.0, default=5.0)  # most the player catches up after a stall
    safe_mode: bool = False
    programme: Programme = Programme()

    @model_validator(mode="after")
    def _a_finite_run_names_one_end(self) -> Self:
        if self.max_seasons is not None and self.until_date is not None:
            msg = "give max_seasons or until_date, not both"
            raise ValueError(msg)
        return self

    @property
    def lock_path(self) -> Path:
        """The single-instance lock file beside the database."""
        return self.db_path.with_suffix(self.db_path.suffix + ".lock")

    @property
    def health_path(self) -> Path:
        """The heartbeat file beside the database."""
        return self.db_path.with_suffix(self.db_path.suffix + ".health.json")
