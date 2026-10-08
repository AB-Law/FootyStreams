"""Build name parts from a culture's syllable grammar (pure given a WorldRng)."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.person import Pronunciation
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Gender
from footystreams.seed.names.cultures import NameCulture

VOWEL_LETTERS = frozenset("aeiouyäöüáéíóúàèìòùâêîôûāēīōūěø")
OPEN_ROOT_SHARE = 0.5  # chance a root's last syllable is open (no coda) when joined to a suffix
OPEN_INTERNAL_SHARE = 0.7  # inner syllables are mostly open, which keeps names pronounceable
OPEN_COMPOUND_SHARE = 0.4


@dataclass(frozen=True, slots=True)
class NameParts:
    """A generated name component: the letters and the syllables it was built from."""

    text: str
    syllables: tuple[str, ...]


def _starts_with_vowel(text: str) -> bool:
    return bool(text) and text[0] in VOWEL_LETTERS


def _syllable(rng: WorldRng, culture: NameCulture, *, open_syllable: bool = False) -> str:
    onset = rng.choice_weighted(culture.onsets)
    nucleus = rng.choice_weighted(culture.nuclei)
    coda = "" if open_syllable else rng.choice_weighted(culture.codas)
    return onset + nucleus + coda


def _inner_syllable(rng: WorldRng, culture: NameCulture) -> str:
    return _syllable(rng, culture, open_syllable=rng.bernoulli(OPEN_INTERNAL_SHARE))


def _ending_table(culture: NameCulture, gender: Gender, rng: WorldRng) -> dict[str, float]:
    if gender is Gender.MALE:
        return culture.given.male_endings
    if gender is Gender.FEMALE:
        return culture.given.female_endings
    return culture.given.male_endings if rng.bernoulli(0.5) else culture.given.female_endings


def _final_syllable(rng: WorldRng, culture: NameCulture, ending: str) -> str:
    """Last syllable: onset + ending, with a nucleus when the ending starts with a consonant."""
    if not ending:
        return _syllable(rng, culture)
    onset = rng.choice_weighted(culture.onsets)
    if _starts_with_vowel(ending):
        return onset + ending
    return onset + rng.choice_weighted(culture.nuclei) + ending


def _capitalise(text: str) -> str:
    return text[:1].upper() + text[1:]


def given_name(rng: WorldRng, culture: NameCulture, gender: Gender) -> NameParts:
    """A given name: (n-1) free syllables and a gendered ending."""
    count = rng.choice_weighted(culture.given.syllables)
    endings = _ending_table(culture, gender, rng)
    syllables = [_inner_syllable(rng, culture) for _ in range(count - 1)]
    syllables.append(_final_syllable(rng, culture, rng.choice_weighted(endings)))
    return NameParts(_capitalise("".join(syllables)), tuple(syllables))


def _join_root_and_suffix(root: str, suffix: str) -> str:
    """Drop the root's trailing vowels when the suffix starts with one, to avoid vowel pile-ups."""
    if _starts_with_vowel(suffix):
        root = root.rstrip("".join(VOWEL_LETTERS)) or root
    return root + suffix


def _root(rng: WorldRng, culture: NameCulture) -> tuple[str, ...]:
    count = rng.choice_weighted(culture.surname.root_syllables)
    syllables = [_inner_syllable(rng, culture) for _ in range(count - 1)]
    syllables.append(_syllable(rng, culture, open_syllable=rng.bernoulli(OPEN_ROOT_SHARE)))
    return tuple(syllables)


def _root_suffix_core(rng: WorldRng, culture: NameCulture) -> NameParts:
    root = _root(rng, culture)
    suffix = rng.choice_weighted(culture.surname.suffixes)
    text = _join_root_and_suffix("".join(root), suffix)
    return NameParts(text, (*root, suffix))


def _compound_core(rng: WorldRng, culture: NameCulture) -> NameParts:
    first = _syllable(rng, culture, open_syllable=rng.bernoulli(OPEN_COMPOUND_SHARE))
    second = _syllable(rng, culture)
    return NameParts(first + second, (first, second))


def _single_core(rng: WorldRng, culture: NameCulture, shape: str) -> NameParts:
    if shape == "compound":
        return _compound_core(rng, culture)
    return _root_suffix_core(rng, culture)


def surname_core(rng: WorldRng, culture: NameCulture) -> NameParts:
    """A surname without particle or hyphenation: root+suffix or a two-syllable compound."""
    shapes = {key: weight for key, weight in culture.surname.shapes.items() if key != "particle"}
    return _single_core(rng, culture, rng.choice_weighted(shapes))


def place_core(rng: WorldRng, culture: NameCulture) -> NameParts:
    """A place name uses the surname machinery: it should sound like the people who live there."""
    return surname_core(rng, culture)


@dataclass(frozen=True, slots=True)
class SurnameParts:
    """A full surname: display text, the short form used on air, and its syllables."""

    full: str
    short: str
    syllables: tuple[str, ...]
    stress_syllable: int


def _stress_index(culture: NameCulture, count: int) -> int:
    if culture.stress == "first":
        return 0
    if culture.stress == "last":
        return count - 1
    return max(0, count - 2)


def _hyphenate(rng: WorldRng, culture: NameCulture, first: NameParts) -> NameParts:
    second = surname_core(rng, culture)
    return NameParts(
        f"{_capitalise(first.text)}-{_capitalise(second.text)}",
        (*first.syllables, *second.syllables),
    )


def surname(rng: WorldRng, culture: NameCulture) -> SurnameParts:
    """A surname: plain core, hyphenated pair, or particle + core (per the culture's weights)."""
    shape = rng.choice_weighted(culture.surname.shapes)
    core = surname_core(rng, culture)
    stress = _stress_index(culture, len(core.syllables))
    if shape == "particle" and culture.surname.particles:
        particle = rng.choice(culture.surname.particles)
        text = f"{particle} {_capitalise(core.text)}"
        return SurnameParts(text, _capitalise(core.text), (particle, *core.syllables), stress + 1)
    if rng.bernoulli(culture.hyphen_share):
        pair = _hyphenate(rng, culture, core)
        return SurnameParts(pair.text, pair.text, pair.syllables, stress)
    return SurnameParts(_capitalise(core.text), _capitalise(core.text), core.syllables, stress)


def with_diacritics(rng: WorldRng, culture: NameCulture, text: str) -> str:
    """Swap letters for the culture's accented forms, each occurrence at ``diacritic_rate``."""
    if not culture.diacritics:
        return text
    return "".join(
        culture.diacritics[char]
        if char in culture.diacritics and rng.bernoulli(culture.diacritic_rate)
        else char
        for char in text
    )


def pronunciation(syllables: tuple[str, ...], stress_syllable: int) -> Pronunciation:
    """Respelling with the stressed syllable in capitals, e.g. ``kar-VEN``."""
    marked = [
        part.upper() if index == stress_syllable else part.lower()
        for index, part in enumerate(syllables)
    ]
    return Pronunciation(
        respelling="-".join(marked)[:40], ipa=None, stress_syllable=stress_syllable
    )
