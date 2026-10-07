"""Who is closest to a point: small leaf helpers shared by the resolvers."""

from __future__ import annotations

from footystreams.sim.geometry import Point, distance_m
from footystreams.sim.play import Play
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.state import PlayerState


def nearest_defender_to(play: Play, point: Point) -> PlayerState:
    """Return the defender closest to a point (wins a loose ball there)."""
    return nearest_opponents(play.state.defenders, point[0], point[1], 1)[0][1]


def closest_of(players: list[PlayerState], point: Point) -> PlayerState:
    """Return the player nearest to a point; ties go to the lower slot."""
    return min(
        players,
        key=lambda player: (distance_m(point[0], point[1], player.x, player.y), player.slot),
    )
