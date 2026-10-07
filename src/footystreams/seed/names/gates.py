"""Quality gates for generated names: pronounceability, blocklist and real-world denylist."""

from __future__ import annotations

from footystreams.domain.textfold import plain

MIN_COMPONENT_LENGTH = 3
MAX_COMPONENT_LENGTH = 14
MIN_VOWEL_SHARE = 0.28
MAX_VOWEL_SHARE = 0.62
MAX_CONSONANT_RUN = 4
MAX_VOWEL_RUN = 3
TRIPLE = 3
PLAIN_VOWELS = frozenset("aeiouy")


def _has_triple_letter(letters: str) -> bool:
    return any(letters[i] == letters[i + 1] == letters[i + 2] for i in range(len(letters) - 2))


def _longest_run(letters: str, *, vowels: bool) -> int:
    longest = current = 0
    for char in letters:
        current = current + 1 if (char in PLAIN_VOWELS) == vowels else 0
        longest = max(longest, current)
    return longest


def is_pronounceable(component: str) -> bool:
    """Length, vowel share, consonant/vowel runs and triple letters of one name component."""
    letters = plain(component)
    if not MIN_COMPONENT_LENGTH <= len(letters) <= MAX_COMPONENT_LENGTH:
        return False
    vowel_share = sum(char in PLAIN_VOWELS for char in letters) / len(letters)
    return (
        MIN_VOWEL_SHARE <= vowel_share <= MAX_VOWEL_SHARE
        and not _has_triple_letter(letters)
        and _longest_run(letters, vowels=False) <= MAX_CONSONANT_RUN
        and _longest_run(letters, vowels=True) <= MAX_VOWEL_RUN
    )


def contains_blocked(text: str, blocklist: frozenset[str]) -> bool:
    """True when any blocklisted substring appears in the plain form of ``text``."""
    letters = plain(text)
    return any(word in letters for word in blocklist)


def is_denied(candidates: tuple[str, ...], denylist: frozenset[str]) -> bool:
    """True when any candidate (surname, known_as, full name) is a real-world name on the list."""
    return any(plain(candidate) in denylist for candidate in candidates)


def normalise_list(lines: tuple[str, ...]) -> frozenset[str]:
    """Plain-letter set from the lines of a denylist or blocklist file."""
    return frozenset(plain(line) for line in lines if plain(line))
