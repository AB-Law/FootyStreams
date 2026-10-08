"""The name book: draws unique, gate-checked names and remembers what is taken.

Mutable on purpose: uniqueness ("known_as is unique within a world", a surname repeats at most
twice) is world-wide state, so one ``NameBook`` is threaded through a whole generation run.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from footystreams.domain.person import Pronunciation
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Gender
from footystreams.seed.names import grammar
from footystreams.seed.names.cultures import NameCulture, load_cultures
from footystreams.seed.names.gates import (
    contains_blocked,
    is_denied,
    is_pronounceable,
    normalise_list,
)
from footystreams.seed.static.files import read_text_lines

MAX_ATTEMPTS = 80
MAX_SURNAME_REPEATS = 2


class NameGenerationError(RuntimeError):
    """No acceptable name could be drawn within the attempt budget."""


@dataclass(frozen=True, slots=True)
class GeneratedName:
    """A complete person name with the on-air short form and a TTS pronunciation hint."""

    first_name: str
    last_name: str
    known_as: str
    pronunciation: Pronunciation
    culture: str
    surname_short: str


@dataclass(frozen=True, slots=True)
class NameBookState:
    """A saved copy of what a NameBook has handed out."""

    known_as: frozenset[str]
    surnames: Counter[str]
    places: frozenset[str]


class NameBook:
    """Draws names for people and places from the invented cultures."""

    def __init__(
        self,
        cultures: dict[str, NameCulture],
        denylist: frozenset[str],
        blocklist: frozenset[str],
    ) -> None:
        """Create an empty book over the given grammars and filters."""
        self._cultures = cultures
        self._denylist = denylist
        self._blocklist = blocklist
        self._known_as: set[str] = set()
        self._surnames: Counter[str] = Counter()
        self._places: set[str] = set()

    @classmethod
    def from_static(cls, directory: Path | None = None) -> NameBook:
        """Build a book from ``data/static`` (cultures, denylist, blocklist)."""
        return cls(
            load_cultures(directory),
            normalise_list(read_text_lines("denylist.txt", directory)),
            normalise_list(read_text_lines("blocklist.txt", directory)),
        )

    def checkpoint(self) -> NameBookState:
        """Copy the uniqueness state so a discarded generation attempt can be undone."""
        return NameBookState(
            frozenset(self._known_as), Counter(self._surnames), frozenset(self._places)
        )

    def restore(self, state: NameBookState) -> None:
        """Return to a previous ``checkpoint``."""
        self._known_as = set(state.known_as)
        self._surnames = Counter(state.surnames)
        self._places = set(state.places)

    def culture(self, key: str) -> NameCulture:
        """Look up a culture by key."""
        try:
            return self._cultures[key]
        except KeyError as error:
            msg = f"unknown name culture {key!r}"
            raise NameGenerationError(msg) from error

    def culture_keys(self, kind: str) -> tuple[str, ...]:
        """Sorted culture keys of one kind (``region`` or ``nation``)."""
        return tuple(sorted(key for key, item in self._cultures.items() if item.kind == kind))

    def is_free(self, known_as: str) -> bool:
        """True when no person already uses ``known_as``."""
        return known_as not in self._known_as

    def claim(self, known_as: str) -> bool:
        """Reserve a known_as for a renamed person; False when it is already taken."""
        if not self.is_free(known_as):
            return False
        self._known_as.add(known_as)
        return True

    def person(
        self,
        rng: WorldRng,
        culture_key: str,
        gender: Gender,
        *,
        family_of: GeneratedName | None = None,
    ) -> GeneratedName:
        """Draw a unique person name; ``family_of`` reuses that person's surname (kin)."""
        culture = self.culture(culture_key)
        for _ in range(MAX_ATTEMPTS):
            candidate = self._candidate(rng, culture, culture_key, gender, family_of)
            if candidate is not None and self._accept(candidate, is_family=family_of is not None):
                return candidate
        msg = f"no acceptable {culture_key} name after {MAX_ATTEMPTS} attempts"
        raise NameGenerationError(msg)

    def place(self, rng: WorldRng, culture_key: str) -> str:
        """Draw a unique place name in the style of a culture."""
        culture = self.culture(culture_key)
        for _ in range(MAX_ATTEMPTS):
            text = grammar.place_core(rng, culture).text.capitalize()
            if text in self._places or not self._passes_filters(text, (text,)):
                continue
            self._places.add(text)
            return grammar.with_diacritics(rng, culture, text)
        msg = f"no acceptable {culture_key} place name after {MAX_ATTEMPTS} attempts"
        raise NameGenerationError(msg)

    def _passes_filters(self, text: str, deny_candidates: tuple[str, ...]) -> bool:
        return (
            is_pronounceable(text)
            and not contains_blocked(text, self._blocklist)
            and not is_denied(deny_candidates, self._denylist)
        )

    def _candidate(
        self,
        rng: WorldRng,
        culture: NameCulture,
        culture_key: str,
        gender: Gender,
        family_of: GeneratedName | None,
    ) -> GeneratedName | None:
        first = grammar.given_name(rng, culture, gender)
        if family_of is None:
            last = grammar.surname(rng, culture)
            short, full = last.short, last.full
            stress_syllables, stress = last.syllables, last.stress_syllable
        else:
            short, full = family_of.surname_short, family_of.last_name
            stress_syllables, stress = (), 0
        if not all(
            self._passes_filters(part, (part, f"{first.text}{part}"))
            for part in (first.text, *short.split("-"))
        ):
            return None
        first_text = grammar.with_diacritics(rng, culture, first.text)
        last_text = full if family_of else grammar.with_diacritics(rng, culture, full)
        short_text = short if family_of else grammar.with_diacritics(rng, culture, short)
        known_as = short_text if self.is_free(short_text) else f"{first_text} {short_text}"
        spoken = (
            family_of.pronunciation
            if family_of
            else grammar.pronunciation(stress_syllables, stress)
        )
        return GeneratedName(first_text, last_text, known_as, spoken, culture_key, short_text)

    def _accept(self, name: GeneratedName, *, is_family: bool) -> bool:
        if not self.is_free(name.known_as):
            return False
        if not is_family and self._surnames[name.surname_short] >= MAX_SURNAME_REPEATS:
            return False
        self._known_as.add(name.known_as)
        self._surnames[name.surname_short] += 1
        return True
