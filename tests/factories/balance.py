"""Builders for the balance harness tests: match samples built by hand."""

from __future__ import annotations

from dataclasses import replace

from footystreams.balance.sample import MatchSample, SideSample


def make_side(**changes: float) -> SideSample:
    """A quiet, ordinary side; change any field by name."""
    side = SideSample(
        goals=1,
        shots=12,
        on_target=4,
        passes=400,
        passes_completed=320.0,
        possession=0.5,
        fouls=11,
        corners=5,
        offsides=2,
        yellows=2,
        reds=0,
        substitutions=4,
    )
    return replace(side, **changes)  # type: ignore[arg-type]


def make_sample(
    home: SideSample | None = None, away: SideSample | None = None, **changes: float
) -> MatchSample:
    """A drawn, even match; change match-level fields by name."""
    sample = MatchSample(
        home=home or make_side(),
        away=away or make_side(),
        gap=0.0,
        penalties=0,
        penalties_scored=0,
        injuries=0,
        goals_second_half=1,
        goals_late=0,
        added_first_half=2,
        added_second_half=4,
        early_tactical_subs=0,
    )
    return replace(sample, **changes)  # type: ignore[arg-type]
