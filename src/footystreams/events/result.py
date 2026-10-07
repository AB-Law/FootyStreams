"""MatchResult freeze contract for parallel tracks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Self

from pydantic import model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.match import SetupRef
from footystreams.domain.versions import SIM_VERSION
from footystreams.events.summary import MatchSummary
from footystreams.events.types import MatchEvent


class MatchResult(DomainModel):
    """Complete output of run_match (no sim end_state)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "events": "S",
        "summary": "L",
        "setup_ref": "L",
        "seed": "S",
        "sim_version": "S",
        "config_hash": "S",
        "log_digest": "L",
    }

    events: tuple[MatchEvent, ...]
    summary: MatchSummary
    setup_ref: SetupRef
    seed: int
    sim_version: str = SIM_VERSION
    config_hash: str
    log_digest: str

    @model_validator(mode="after")
    def _digest_matches_summary(self) -> Self:
        if self.log_digest != self.summary.log_digest:
            msg = "MatchResult.log_digest must equal summary.log_digest"
            raise ValueError(msg)
        if self.config_hash != self.summary.config_hash:
            msg = "MatchResult.config_hash must equal summary.config_hash"
            raise ValueError(msg)
        if self.seed != self.summary.seed:
            msg = "MatchResult.seed must equal summary.seed"
            raise ValueError(msg)
        return self
