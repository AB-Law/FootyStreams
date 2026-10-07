"""Usage registry completeness for domain and event models."""

from __future__ import annotations

from footystreams.domain.registry import DOMAIN_MODELS
from footystreams.domain.usage import (
    discover_models,
    invalid_usage_tags,
    unknown_usage_keys,
    untagged_fields,
)


def _usage_problems(models: tuple[type, ...]) -> list[str]:
    problems: list[str] = []
    for model in models:
        name = f"{model.__module__}.{model.__name__}"
        problems.extend(
            f"{name}.{field} missing from __usage__" for field in sorted(untagged_fields(model))
        )
        problems.extend(
            f"{name}.__usage__[{field}] is not a model field"
            for field in sorted(unknown_usage_keys(model))
        )
        problems.extend(
            f"{name}.{field} has invalid usage tag" for field in sorted(invalid_usage_tags(model))
        )
    return problems


def test_domain_registry__matches_discovered_domain_models() -> None:
    discovered = discover_models("footystreams.domain")
    assert discovered == DOMAIN_MODELS
    assert len(DOMAIN_MODELS) >= 100


def test_field_usage_registry__domain_models_complete() -> None:
    problems = _usage_problems(DOMAIN_MODELS)
    assert not problems, "\n".join(problems)


def test_field_usage_registry__event_models_complete() -> None:
    """Events are out of DOMAIN_MODELS (exported via MatchEvent) but still tagged."""
    event_models = discover_models("footystreams.events")
    problems = _usage_problems(event_models)
    assert not problems, "\n".join(problems)
    assert len(event_models) >= 40
