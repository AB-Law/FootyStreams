"""Usage registry completeness for domain models."""

from __future__ import annotations

from footystreams.domain.registry import DOMAIN_MODELS
from footystreams.domain.usage import invalid_usage_tags, unknown_usage_keys, untagged_fields


def test_field_usage_registry__no_untagged_or_unknown_fields() -> None:
    problems: list[str] = []
    for model in DOMAIN_MODELS:
        name = model.__name__
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
    assert not problems, "\n".join(problems)
