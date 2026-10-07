"""Canonical JSON serialization for digests, schema export and world IO."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(value: Any) -> str:
    r"""Serialize ``value`` with sorted keys and compact separators (LF only).

    Used for ``log_digest``, schema drift comparison and later seed/world
    hashing. Callers must not strip or rewrite the trailing absence of a
    newline — writers that emit files should append ``\n`` themselves.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
