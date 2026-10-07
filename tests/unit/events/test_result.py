"""Tests for MatchResult and make_match_result."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from footystreams.events.result import MatchResult
from tests.factories.result import make_match_result


def test_make_match_result__validates() -> None:
    result = make_match_result()
    assert result.log_digest == result.summary.log_digest
    assert MatchResult.model_validate_json(result.model_dump_json()) == result


def test_match_result__digest_mismatch__rejected() -> None:
    result = make_match_result()
    payload = result.model_dump(mode="json")
    payload["log_digest"] = "c" * 64
    with pytest.raises(ValidationError):
        MatchResult.model_validate(payload)
