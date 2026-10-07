"""Catalogue of domain models for schema export and usage completeness.

``DOMAIN_MODELS`` is discovered from ``footystreams.domain`` so adding a new
``DomainModel`` without a complete ``__usage__`` fails the usage tests.
Event models live under ``footystreams.events`` and are checked separately
(they are exported via the ``MatchEvent`` union, not as ``schemas/models/*``).
"""

from __future__ import annotations

from footystreams.domain.base import DomainModel
from footystreams.domain.usage import discover_models

DOMAIN_MODELS: tuple[type[DomainModel], ...] = discover_models("footystreams.domain")
