from __future__ import annotations

import json
from pathlib import Path

import pytest

from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.seed.config import GENERATOR_VERSION
from footystreams.seed.world_io import (
    MANIFEST_FILE,
    WorldFileError,
    build_manifest,
    content_hash,
    pretty_json,
    read_manifest,
    read_world,
    render_tables,
    write_world,
)
from tests.factories.world import make_world


def test_pretty_json__sorted_keys_two_space_indent_trailing_newline() -> None:
    text = pretty_json({"b": 1, "a": [1, 2]})
    assert text == '{\n  "a": [\n    1,\n    2\n  ],\n  "b": 1\n}\n'


def test_pretty_json__keeps_non_ascii_letters() -> None:
    assert "š" in pretty_json({"name": "Khaški"})


def test_render_tables__is_deterministic_and_uses_lf_only() -> None:
    first = render_tables(make_world())
    second = render_tables(make_world())
    assert first == second
    assert all("\r" not in text and text.endswith("\n") for text in first.values())


def test_content_hash__changes_with_any_file_and_with_file_names() -> None:
    files = {"a.json": "1\n", "b.json": "2\n"}
    assert content_hash(files) == content_hash(dict(reversed(files.items())))
    assert content_hash(files) != content_hash({**files, "b.json": "3\n"})
    assert content_hash(files) != content_hash({"a.json": "1\n", "c.json": "2\n"})


def test_build_manifest__counts_versions_and_hash() -> None:
    world = make_world()
    manifest = build_manifest(world)
    assert manifest.world_seed == 1
    assert manifest.generator_version == GENERATOR_VERSION
    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.counts["players"] == len(world.players)
    assert manifest.counts["memories"] == 0
    assert manifest.content_sha256 == content_hash(render_tables(world))


def test_write_then_read__round_trips_the_world(tmp_path: Path) -> None:
    world = make_world()
    manifest = write_world(world, tmp_path / "w")
    loaded = read_world(tmp_path / "w")
    assert loaded == world
    assert build_manifest(loaded) == manifest
    assert read_manifest(tmp_path / "w") == manifest


def test_write_world__files_are_the_rendered_text_byte_for_byte(tmp_path: Path) -> None:
    world = make_world()
    write_world(world, tmp_path)
    for name, text in render_tables(world).items():
        assert (tmp_path / name).read_bytes() == text.encode("utf-8")
    assert json.loads((tmp_path / MANIFEST_FILE).read_text(encoding="utf-8"))["world_seed"] == 1


def test_read_world__edited_file__fails_the_hash_check(tmp_path: Path) -> None:
    write_world(make_world(), tmp_path)
    clubs = tmp_path / "clubs.json"
    clubs.write_bytes(clubs.read_bytes().replace(b'"name"', b'"name "', 1))
    with pytest.raises(WorldFileError, match="content_sha256"):
        read_world(tmp_path)


def test_read_world__invalid_rows_are_reported_with_the_file(tmp_path: Path) -> None:
    write_world(make_world(), tmp_path)
    (tmp_path / "nations.json").write_text('[{"id": "bad"}]\n', encoding="utf-8")
    with pytest.raises(WorldFileError, match=r"nations\.json"):
        read_world(tmp_path, verify_hash=False)


def test_read_world__missing_file__names_it(tmp_path: Path) -> None:
    write_world(make_world(), tmp_path)
    (tmp_path / "players.json").unlink()
    with pytest.raises(WorldFileError, match=r"players\.json"):
        read_world(tmp_path)


def test_read_manifest__invalid_content__raises(tmp_path: Path) -> None:
    (tmp_path / MANIFEST_FILE).write_text("{}\n", encoding="utf-8")
    with pytest.raises(WorldFileError, match="invalid manifest"):
        read_manifest(tmp_path)
