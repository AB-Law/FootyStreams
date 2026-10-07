"""Golden digests: a changed log for a pinned (pairing, seed, config) is a deliberate decision."""

import pytest

from footystreams.cli.golden import compute_golden, differences, load_golden
from footystreams.domain.versions import SIM_VERSION

pytestmark = pytest.mark.golden


def test_golden__digests_match_a_fresh_run() -> None:
    stored = load_golden()
    assert stored is not None, "tests/golden/digests.json missing: run `uv run golden update`"
    changed = differences(compute_golden(), stored)
    assert not changed, (
        f"output changed for {changed}: bump SIM_VERSION and run `uv run golden update` "
        "if this is intended"
    )


def test_golden__file_was_written_for_the_current_sim_version() -> None:
    stored = load_golden()
    assert stored is not None
    assert stored["sim_version"] == SIM_VERSION
