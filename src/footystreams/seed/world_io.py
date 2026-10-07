"""Read and write a World as canonical JSON files plus a manifest with a content hash.

Canonical means: sorted keys, two-space indent, UTF-8, LF endings and a trailing newline, so diffs
are reviewable and the hash is identical on every platform.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.manager import Manager
from footystreams.domain.media import MediaPersonality
from footystreams.domain.memory import MemoryRecord
from footystreams.domain.player import Player
from footystreams.domain.referee import Referee
from footystreams.domain.relationship import Relationship
from footystreams.domain.staff import StaffMember
from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.domain.world import City, Nation, SquadEntry, World, WorldManifest
from footystreams.seed.config import GENERATOR_VERSION

MANIFEST_FILE = "manifest.json"
JSON_INDENT = 2


class WorldFileError(ValueError):
    """A world directory is missing a file, has invalid content or fails its hash."""


@dataclass(frozen=True, slots=True)
class _Table:
    """One world file: its name, the model of its rows and how to get/set the rows on a World."""

    file: str
    model: type[BaseModel]
    rows: Callable[[World], Sequence[BaseModel]]
    field: str


_TABLES: tuple[_Table, ...] = (
    _Table("nations.json", Nation, lambda w: w.nations, "nations"),
    _Table("cities.json", City, lambda w: w.cities, "cities"),
    _Table("competitions.json", Competition, lambda w: w.competitions, "competitions"),
    _Table("seasons.json", Season, lambda w: w.seasons, "seasons"),
    _Table("clubs.json", Club, lambda w: w.clubs, "clubs"),
    _Table("squad_entries.json", SquadEntry, lambda w: w.squad_entries, "squad_entries"),
    _Table("players.json", Player, lambda w: w.players, "players"),
    _Table("managers.json", Manager, lambda w: w.managers, "managers"),
    _Table("staff.json", StaffMember, lambda w: w.staff, "staff"),
    _Table("referees.json", Referee, lambda w: w.referees, "referees"),
    _Table("media.json", MediaPersonality, lambda w: w.media, "media"),
    _Table("relationships.json", Relationship, lambda w: w.relationships, "relationships"),
    _Table("memories.json", MemoryRecord, lambda w: w.memories, "memories"),
    _Table("ledger_opening.json", LedgerEntry, lambda w: w.ledger_opening, "ledger_opening"),
)


def pretty_json(value: object) -> str:
    """Canonical text of a JSON value: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(value, sort_keys=True, indent=JSON_INDENT, ensure_ascii=False) + "\n"


def render_tables(world: World) -> dict[str, str]:
    """The canonical text of every data file (everything except the manifest)."""
    return {
        table.file: pretty_json([row.model_dump(mode="json") for row in table.rows(world)])
        for table in _TABLES
    }


def content_hash(files: Mapping[str, str]) -> str:
    """SHA-256 over the data files in name order, each framed by its name and length."""
    digest = hashlib.sha256()
    for name in sorted(files):
        text = files[name]
        digest.update(f"{name}\n{len(text.encode('utf-8'))}\n".encode())
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def build_manifest(world: World, files: Mapping[str, str] | None = None) -> WorldManifest:
    """The manifest for a world (rendering the files itself when they are not passed in)."""
    rendered = files if files is not None else render_tables(world)
    return WorldManifest(
        world_seed=world.world_seed,
        generator_version=GENERATOR_VERSION,
        schema_version=SCHEMA_VERSION,
        counts={table.field: len(table.rows(world)) for table in _TABLES},
        content_sha256=content_hash(rendered),
        created_in_world=world.created_in_world,
    )


def write_world(world: World, directory: Path) -> WorldManifest:
    """Write every file and the manifest into ``directory`` (created if needed)."""
    files = render_tables(world)
    manifest = build_manifest(world, files)
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / name).write_bytes(text.encode("utf-8"))
    manifest_text = pretty_json(manifest.model_dump(mode="json"))
    (directory / MANIFEST_FILE).write_bytes(manifest_text.encode("utf-8"))
    return manifest


def _read_text(directory: Path, name: str) -> str:
    try:
        return (directory / name).read_bytes().decode("utf-8")
    except OSError as error:
        msg = f"cannot read {directory / name}: {error}"
        raise WorldFileError(msg) from error


def read_manifest(directory: Path) -> WorldManifest:
    """Read and validate ``manifest.json``."""
    try:
        return WorldManifest.model_validate_json(_read_text(directory, MANIFEST_FILE))
    except ValidationError as error:
        msg = f"invalid manifest in {directory}: {error}"
        raise WorldFileError(msg) from error


def _rows[Row: BaseModel](
    model: type[Row], file: str, texts: Mapping[str, str], directory: Path
) -> tuple[Row, ...]:
    try:
        return tuple(TypeAdapter(list[model]).validate_json(texts[file]))  # type: ignore[valid-type]
    except ValidationError as error:
        msg = f"invalid rows in {directory / file}: {error}"
        raise WorldFileError(msg) from error


def read_world(directory: Path, *, verify_hash: bool = True) -> World:
    """Read a world directory, validating every row; the content hash must match the manifest."""
    manifest = read_manifest(directory)
    texts = {table.file: _read_text(directory, table.file) for table in _TABLES}
    if verify_hash and content_hash(texts) != manifest.content_sha256:
        msg = f"{directory}: files do not match the manifest content_sha256"
        raise WorldFileError(msg)

    def read[Row: BaseModel](model: type[Row], file: str) -> tuple[Row, ...]:
        return _rows(model, file, texts, directory)

    return World(
        world_seed=manifest.world_seed,
        created_in_world=manifest.created_in_world,
        nations=read(Nation, "nations.json"),
        cities=read(City, "cities.json"),
        competitions=read(Competition, "competitions.json"),
        seasons=read(Season, "seasons.json"),
        clubs=read(Club, "clubs.json"),
        squad_entries=read(SquadEntry, "squad_entries.json"),
        players=read(Player, "players.json"),
        managers=read(Manager, "managers.json"),
        staff=read(StaffMember, "staff.json"),
        referees=read(Referee, "referees.json"),
        media=read(MediaPersonality, "media.json"),
        relationships=read(Relationship, "relationships.json"),
        memories=read(MemoryRecord, "memories.json"),
        ledger_opening=read(LedgerEntry, "ledger_opening.json"),
    )
