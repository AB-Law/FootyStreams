"""Typed match event stream models (no simulation logic)."""

from footystreams.events.result import MatchResult
from footystreams.events.summary import MatchSummary
from footystreams.events.types import MATCH_EVENT_ADAPTER, MatchEvent

__all__ = ["MATCH_EVENT_ADAPTER", "MatchEvent", "MatchResult", "MatchSummary"]
