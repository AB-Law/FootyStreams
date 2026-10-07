"""LLM/extension proposal envelope (validated later by an applier)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import GameDate, ProposalId


class ProposalStatus(StrEnum):
    """Lifecycle of a proposal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"


class ProposalSource(DomainModel):
    """Who proposed the change."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "component": "R",
        "model_id": "R",
        "prompt_hash": "R",
    }

    component: str
    model_id: str
    prompt_hash: str


class Proposal(DomainModel):
    """Bounded proposal waiting for deterministic application."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "R",
        "kind": "R",
        "payload": "R",
        "proposed_by": "R",
        "created_on": "R",
        "status": "R",
        "rejection_reason": "R",
    }

    id: ProposalId
    kind: str = Field(min_length=1, max_length=40)
    payload: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    proposed_by: ProposalSource
    created_on: GameDate
    status: ProposalStatus = ProposalStatus.PENDING
    rejection_reason: str | None = None
