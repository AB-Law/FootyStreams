"""Fold names to plain lower-case ASCII letters, so filters see what a reader sees."""

from __future__ import annotations

import unicodedata

_SPECIAL_FOLDS = {"ø": "o", "ß": "ss", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d"}


def plain(text: str) -> str:
    """Lower-case letters only, diacritics folded (``Ørsted-Šimák`` becomes ``orstedsimak``)."""
    folded = "".join(_SPECIAL_FOLDS.get(char, char) for char in text.lower())
    decomposed = unicodedata.normalize("NFKD", folded)
    return "".join(char for char in decomposed if char.isascii() and char.isalpha())
