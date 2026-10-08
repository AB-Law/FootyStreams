import pytest

from footystreams.events.derive.threat import (
    GRID_COLUMNS,
    GRID_ROWS,
    centrality,
    frame_value,
    threat,
    zone_of,
)
from footystreams.sim.geometry import centrality as sim_centrality


@pytest.mark.parametrize("frame_y", [0.0, 0.1, 0.5, 0.73, 1.0])
def test_centrality__matches_the_simulators_geometry(frame_y: float) -> None:
    assert centrality(frame_y) == sim_centrality(frame_y)


def test_threat__grows_toward_goal_and_is_highest_in_the_centre() -> None:
    assert threat(0.9, 0.5) > threat(0.5, 0.5) > threat(0.1, 0.5)
    assert threat(0.9, 0.5) > threat(0.9, 0.05)


def test_frame_value__mirrors_when_attacking_the_other_way() -> None:
    assert frame_value(0.2, 1) == 0.2
    assert frame_value(0.2, -1) == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("frame_x", "frame_y", "zone"),
    [(0.0, 0.0, 0), (0.0, 0.99, GRID_ROWS - 1), (0.99, 0.0, (GRID_COLUMNS - 1) * GRID_ROWS)],
)
def test_zone_of__corners_of_the_grid(frame_x: float, frame_y: float, zone: int) -> None:
    assert zone_of(frame_x, frame_y) == zone


def test_zone_of__the_far_edge_folds_into_the_last_zone() -> None:
    assert zone_of(1.0, 1.0) == GRID_COLUMNS * GRID_ROWS - 1
    assert zone_of(-0.5, 2.0) == GRID_ROWS - 1
