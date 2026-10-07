from __future__ import annotations

import pytest

from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.persistence import codec
from footystreams.persistence.codec import decode, encode
from footystreams.persistence.errors import SchemaVersionError
from tests.factories.world import make_world

WORLD = make_world(1)


def test_encode_decode__round_trips_a_player_exactly() -> None:
    player = WORLD.players[0]
    stored = encode(player)
    restored = decode(
        type(player), stored, table="players", key=str(player.id), stored=SCHEMA_VERSION
    )
    assert restored == player


def test_encode__is_canonical_sorted_compact_json() -> None:
    club = WORLD.clubs[0]
    text = encode(club)
    assert text == encode(club)
    assert text.startswith('{"academy":')
    assert "\n" not in text


def test_decode__other_schema_series_without_a_migration__raises() -> None:
    club = WORLD.clubs[0]
    with pytest.raises(SchemaVersionError, match=r"9\.0\.0"):
        decode(type(club), encode(club), table="clubs", key=str(club.id), stored="9.0.0")


def test_decode__patch_difference_within_the_series_reads_directly() -> None:
    club = WORLD.clubs[0]
    major, minor, _ = SCHEMA_VERSION.split(".")
    stored = f"{major}.{minor}.99"
    assert decode(type(club), encode(club), table="clubs", key=str(club.id), stored=stored) == club


def test_decode__a_registered_row_migration_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    club = WORLD.clubs[0]
    monkeypatch.setitem(codec.ROW_MIGRATIONS, ("clubs", "9.0.0"), lambda row: row)
    assert decode(type(club), encode(club), table="clubs", key=str(club.id), stored="9.0.0") == club
