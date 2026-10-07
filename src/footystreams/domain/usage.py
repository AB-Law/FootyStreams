"""S/L/R field-usage registry helpers and model discovery."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from collections.abc import Iterable, Mapping, Sequence
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


def discover_models(*package_names: str) -> tuple[type[DomainModel], ...]:
    """Import ``package_names`` recursively and return every concrete DomainModel.

    Discovery is the source of truth for completeness tests: forgetting to
    register a new model fails the registry equality test rather than silently
    skipping ``__usage__`` checks.
    """
    for package_name in package_names:
        package = importlib.import_module(package_name)
        paths: Sequence[str] | None = getattr(package, "__path__", None)
        if paths is None:
            continue
        for module_info in pkgutil.walk_packages(paths, package_name + "."):
            importlib.import_module(module_info.name)

    seen: set[type[DomainModel]] = set()
    for module in sys.modules.values():
        name = getattr(module, "__name__", "")
        if not any(name == pkg or name.startswith(pkg + ".") for pkg in package_names):
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, DomainModel)
                and obj is not DomainModel
                and any(obj.__module__.startswith(pkg) for pkg in package_names)
            ):
                seen.add(obj)
    return tuple(sorted(seen, key=lambda cls: (cls.__module__, cls.__name__)))


def iter_domain_models(models: Iterable[type[DomainModel]]) -> Iterable[type[DomainModel]]:
    """Yield models unchanged (keeps callers deterministic)."""
    return models
