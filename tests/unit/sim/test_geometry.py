import pytest

from footystreams.sim.geometry import (
    centrality,
    closest_point_on_segment,
    distance_m,
    frame_coordinate,
    goal_distance_m,
    in_penalty_area,
    segment_distance_m,
    squared_distance_m,
)


def test_frame_coordinate__is_its_own_inverse() -> None:
    assert frame_coordinate(frame_coordinate(0.3, -1), -1) == pytest.approx(0.3)
    assert frame_coordinate(0.3, 1) == 0.3


def test_distance_m__full_pitch_length_is_105_metres() -> None:
    assert distance_m(0.0, 0.5, 1.0, 0.5) == pytest.approx(105.0)


def test_squared_distance_m__matches_distance() -> None:
    assert squared_distance_m(0.1, 0.2, 0.4, 0.9) == pytest.approx(
        distance_m(0.1, 0.2, 0.4, 0.9) ** 2
    )


def test_goal_distance_m__penalty_spot_is_eleven_metres() -> None:
    assert goal_distance_m(1.0 - 11.0 / 105.0, 0.5) == pytest.approx(11.0)


def test_segment_distance_m__perpendicular_foot_inside_segment() -> None:
    assert segment_distance_m((0.5, 0.6), (0.0, 0.5), (1.0, 0.5)) == pytest.approx(6.8)


def test_segment_distance_m__beyond_the_end_uses_the_endpoint() -> None:
    assert segment_distance_m((1.2, 0.5), (0.0, 0.5), (1.0, 0.5)) == pytest.approx(21.0)


def test_segment_distance_m__degenerate_segment_is_point_distance() -> None:
    assert segment_distance_m((0.5, 0.5), (0.5, 0.6), (0.5, 0.6)) == pytest.approx(6.8)


def test_in_penalty_area__box_edges() -> None:
    assert in_penalty_area(0.95, 0.5)
    assert not in_penalty_area(0.8, 0.5)
    assert not in_penalty_area(0.95, 0.05)


def test_centrality__centre_one_touchline_zero() -> None:
    assert centrality(0.5) == 1.0
    assert centrality(0.0) == 0.0


def test_closest_point_on_segment__is_the_perpendicular_foot_inside_the_segment() -> None:
    assert closest_point_on_segment((0.5, 0.9), (0.2, 0.5), (0.8, 0.5)) == pytest.approx((0.5, 0.5))


def test_closest_point_on_segment__beyond_the_end_is_the_endpoint() -> None:
    assert closest_point_on_segment((0.95, 0.9), (0.2, 0.5), (0.8, 0.5)) == pytest.approx(
        (0.8, 0.5)
    )


def test_closest_point_on_segment__a_degenerate_segment_is_its_start() -> None:
    assert closest_point_on_segment((0.5, 0.5), (0.2, 0.3), (0.2, 0.3)) == (0.2, 0.3)
