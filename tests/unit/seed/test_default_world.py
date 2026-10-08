"""The committed data/worlds/default world is exactly what seed 1 regenerates."""

from __future__ import annotations

from footystreams.seed.world_io import build_manifest, read_manifest, read_world, render_tables
from footystreams.tools.paths import PROJECT_ROOT
from footystreams.verify import verify_world
from tests.factories.world import make_world, make_world_checks, make_world_targets
from tests.helpers.assertions import assert_no_violations

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"


def test_default_world__manifest_matches_regeneration_from_seed_one() -> None:
    assert read_manifest(DEFAULT_WORLD) == build_manifest(make_world(1))


def test_default_world__files_are_byte_identical_to_a_fresh_render() -> None:
    for name, text in render_tables(make_world(1)).items():
        assert (DEFAULT_WORLD / name).read_bytes() == text.encode("utf-8"), name


def test_default_world__loads_and_is_coherent() -> None:
    world = read_world(DEFAULT_WORLD)
    assert_no_violations(verify_world(world, make_world_checks(), make_world_targets()))
