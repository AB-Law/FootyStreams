"""Text helpers: matching names without accents, and making model output safe for the pixel font."""

from __future__ import annotations

import re
import unicodedata

# Letters the pixel font has no glyph for are folded to something it does have.
_FOLDS = str.maketrans(
    {"ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D"}
    | {
        "ł": "l",
        "Ł": "L",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
    }
    | {"\N{LEFT DOUBLE QUOTATION MARK}": '"', "\N{RIGHT DOUBLE QUOTATION MARK}": '"'}
    | {"\N{EM DASH}": "-", "\N{EN DASH}": "-", "\N{HORIZONTAL ELLIPSIS}": "..."}
)
_ALLOWED = re.compile(r"[^A-Za-z0-9 .,!?:;'\"()%/&+-]")
_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_MARKUP = re.compile(r"\*+([^*]*)\*+|_{2,}|`+")


def fold(text: str) -> str:
    """``text`` without accents and with look-alike letters and marks made plain."""
    plain = unicodedata.normalize("NFD", text).translate(_FOLDS)
    return "".join(char for char in plain if not unicodedata.combining(char))


def speakable(text: str) -> str:
    """``text`` cut down to what the desk can speak and the font can draw: no markup, no emoji."""
    spaced = re.sub(r"\s+", " ", fold(_MARKUP.sub(r"\1", text)))
    return re.sub(r" {2,}", " ", _ALLOWED.sub("", spaced)).strip()


def strip_thinking(text: str) -> str:
    """Model output without any ``<think>`` block a reasoning model put in front of its answer."""
    return _THINKING.sub("", text).strip()


def words(text: str) -> str:
    """The words of ``text`` in lower case without accents or punctuation, to compare wordings."""
    return " ".join(re.findall(r"[a-z0-9]+", fold(text).lower()))
