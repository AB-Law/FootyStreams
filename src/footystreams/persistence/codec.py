"""Pydantic model <-> stored JSON text, with schema-version checking on read."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

from pydantic import BaseModel

from footystreams.domain.canonical import canonical_json
from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.persistence.errors import SchemaVersionError

# (table, stored schema version) -> function turning the stored JSON object into the current one.
# Empty for now: add one whenever a model change needs a data migration (design 04, 4.3).
RowMigration = Callable[[Mapping[str, object]], Mapping[str, object]]
ROW_MIGRATIONS: dict[tuple[str, str], RowMigration] = {}


def encode(entity: BaseModel) -> str:
    """Canonical JSON text of a model (sorted keys, compact)."""
    return canonical_json(entity.model_dump(mode="json"))


def _series(version: str) -> tuple[str, str]:
    major, minor, *_ = version.split(".")
    return major, minor


def decode[Model: BaseModel](
    model: type[Model], text: str, *, table: str, key: str, stored: str
) -> Model:
    """Rebuild a model from stored text written under schema version ``stored``.

    The same major.minor series reads directly. Other versions need a registered row migration;
    without one the read fails loudly rather than guessing.
    """
    if _series(stored) == _series(SCHEMA_VERSION):
        return model.model_validate_json(text)
    migration = ROW_MIGRATIONS.get((table, stored))
    if migration is None:
        raise SchemaVersionError(table, key, stored, SCHEMA_VERSION)
    return model.model_validate(migration(json.loads(text)))
