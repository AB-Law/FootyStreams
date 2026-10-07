"""S/L/R field-usage registry helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import get_args

from pydantic import BaseModel

from footystreams.domain.base import DomainModel, UsageTag

_VALID_TAGS = frozenset(get_args(UsageTag))


def model_fields(model: type[BaseModel]) -> frozenset[str]:
    """Public field names on a Pydantic model (excludes ClassVars)."""
    return frozenset(model.model_fields)


def usage_map(model: type[DomainModel]) -> Mapping[str, UsageTag]:
    """Return the model's ``__usage__`` mapping."""
    return model.__usage__


def untagged_fields(model: type[DomainModel]) -> frozenset[str]:
    """Fields present on the model but missing from ``__usage__``."""
    tagged = frozenset(usage_map(model))
    return model_fields(model) - tagged


def unknown_usage_keys(model: type[DomainModel]) -> frozenset[str]:
    """Keys in ``__usage__`` that are not model fields."""
    return frozenset(usage_map(model)) - model_fields(model)


def invalid_usage_tags(model: type[DomainModel]) -> frozenset[str]:
    """Fields whose usage tag is not S/L/R/S+L."""
    bad: set[str] = set()
    for name, tag in usage_map(model).items():
        if tag not in _VALID_TAGS:
            bad.add(name)
    return frozenset(bad)


def iter_domain_models(models: Iterable[type[DomainModel]]) -> Iterable[type[DomainModel]]:
    """Yield models unchanged (explicit list keeps the registry test deterministic)."""
    return models
