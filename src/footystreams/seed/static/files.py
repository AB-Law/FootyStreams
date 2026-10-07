"""Locate and read the hand-authored YAML tables under data/static."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
STATIC_DIRECTORY = REPOSITORY_ROOT / "data" / "static"


class StaticDataError(ValueError):
    """A static table is missing, unreadable or inconsistent; the message names the file."""


class YamlModel(BaseModel):
    """Base for the raw (pre-conversion) shape of a YAML file: strict, no unknown keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def static_path(name: str, directory: Path | None = None) -> Path:
    """Path of ``data/static/<name>`` (or of ``directory/<name>``)."""
    return (directory or STATIC_DIRECTORY) / name


def read_text_lines(name: str, directory: Path | None = None) -> tuple[str, ...]:
    """Read a plain-text static file as stripped, non-empty, non-comment lines."""
    path = static_path(name, directory)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"cannot read static file {path}: {error}"
        raise StaticDataError(msg) from error
    lines = (line.strip() for line in text.splitlines())
    return tuple(line for line in lines if line and not line.startswith("#"))


def read_yaml(name: str, directory: Path | None = None) -> Mapping[str, object]:
    """Read a YAML mapping from the static directory."""
    path = static_path(name, directory)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"cannot read static table {path}: {error}"
        raise StaticDataError(msg) from error
    if not isinstance(loaded, dict):
        msg = f"static table {path} must be a mapping at the top level"
        raise StaticDataError(msg)
    return loaded


def load_model[Raw: YamlModel](model: type[Raw], name: str, directory: Path | None = None) -> Raw:
    """Read a YAML file and validate it against its raw model, naming the file on failure."""
    document = read_yaml(name, directory)
    try:
        return model.model_validate(document)
    except ValidationError as error:
        msg = f"invalid static table {static_path(name, directory)}:\n{error}"
        raise StaticDataError(msg) from error
