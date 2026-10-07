"""The pinned (pairing, seed, config) cases whose log digests are the golden files."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.sim import SimConfig, config_hash, default_tables, run_match
from tests.factories.sim_teams import make_demo_setup


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """One pinned match: two demo teams, formations and a seed."""

    name: str
    home_strength: int
    away_strength: int
    home_formation: str
    away_formation: str
    seed: int


CASES: tuple[GoldenCase, ...] = (
    GoldenCase("even_433", 60, 60, "433", "433", 7),
    GoldenCase("favourite_442_v_532", 72, 54, "442", "532", 11),
    GoldenCase("mirror_4231_v_352", 62, 62, "4231", "352", 23),
)


def golden_entry(case: GoldenCase) -> dict[str, str | int]:
    """Play a case with the default config and return what is pinned for it."""
    setup = make_demo_setup(
        home_strength=case.home_strength,
        away_strength=case.away_strength,
        home_formation=case.home_formation,
        away_formation=case.away_formation,
    )
    result = run_match(setup, case.seed, SimConfig(), default_tables())
    summary = result.summary
    return {
        "digest": result.log_digest,
        "score": f"{summary.score_home}-{summary.score_away}",
        "events": len(result.events),
    }


def golden_config_hash() -> str:
    """Return the hash of the default config the goldens were produced with."""
    return config_hash(SimConfig())
