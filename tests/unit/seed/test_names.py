from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

import pytest

from footystreams.domain.rng import WorldRng
from footystreams.domain.textfold import plain
from footystreams.domain.types import Gender
from footystreams.seed.names import gates
from footystreams.seed.names.book import GeneratedName, NameBook, NameGenerationError
from footystreams.seed.names.cultures import NameCulture, load_cultures
from footystreams.seed.static.files import read_text_lines

SAMPLES_PER_CULTURE = 120
TRIGRAM_SIMILARITY_CEILING = 0.80


@pytest.fixture(scope="module")
def book_keys() -> tuple[str, ...]:
    return tuple(sorted(load_cultures()))


def _fresh_book() -> NameBook:
    return NameBook.from_static()


def _draw_all(seed: int, per_culture: int) -> dict[str, list[GeneratedName]]:
    book = _fresh_book()
    rng = WorldRng(seed)
    keys = book.culture_keys("region") + book.culture_keys("nation")
    drawn: dict[str, list[GeneratedName]] = {}
    for key in keys:
        stream = rng.fork(key)
        drawn[key] = [
            book.person(stream, key, Gender.MALE if index % 4 else Gender.FEMALE)
            for index in range(per_culture)
        ]
    return drawn


def _trigrams(words: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for word in words:
        padded = f"^{plain(word)}$"
        counts.update(padded[i : i + 3] for i in range(len(padded) - 2))
    return counts


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    dot = sum(left[key] * right[key] for key in left.keys() & right.keys())
    norm = math.sqrt(sum(v * v for v in left.values())) * math.sqrt(
        sum(v * v for v in right.values())
    )
    return dot / norm


def test_cultures__fourteen_with_six_regions_and_eight_nations() -> None:
    cultures = load_cultures()
    kinds = Counter(culture.kind for culture in cultures.values())
    assert kinds == {"region": 6, "nation": 8}


def test_person__same_seed__same_names() -> None:
    first = _draw_all(3, 10)
    second = _draw_all(3, 10)
    assert first == second


def test_person__different_seed__different_names() -> None:
    assert _draw_all(3, 10) != _draw_all(4, 10)


def test_person__known_as_is_unique_across_all_cultures() -> None:
    names = [name for group in _draw_all(5, SAMPLES_PER_CULTURE).values() for name in group]
    known = [name.known_as for name in names]
    assert len(known) == len(set(known))


def test_person__surnames_repeat_at_most_twice() -> None:
    names = [name for group in _draw_all(6, SAMPLES_PER_CULTURE).values() for name in group]
    counts = Counter(name.surname_short for name in names)
    assert max(counts.values()) <= 2


def test_person__every_component_passes_the_form_gate() -> None:
    names = [name for group in _draw_all(7, SAMPLES_PER_CULTURE).values() for name in group]
    parts = [part for name in names for part in (name.first_name, *name.surname_short.split("-"))]
    assert all(gates.is_pronounceable(part) for part in parts)


def test_person__no_name_is_on_the_real_world_denylist() -> None:
    denylist = gates.normalise_list(read_text_lines("denylist.txt"))
    names = [name for group in _draw_all(8, SAMPLES_PER_CULTURE).values() for name in group]
    hits = [
        name for name in names if gates.is_denied((name.known_as, name.surname_short), denylist)
    ]
    assert not hits


def test_person__pronunciation_is_present_and_points_inside_the_name() -> None:
    names = [name for group in _draw_all(9, 40).values() for name in group]
    for name in names:
        syllables = name.pronunciation.respelling.split("-")
        assert name.pronunciation.respelling
        assert 0 <= name.pronunciation.stress_syllable < len(syllables)


def test_person__cultures_look_different_by_character_trigrams() -> None:
    groups = _draw_all(10, SAMPLES_PER_CULTURE)
    profiles = {key: _trigrams([n.surname_short for n in names]) for key, names in groups.items()}
    similar = [
        (a, b, round(_cosine(profiles[a], profiles[b]), 2))
        for a, b in combinations(sorted(profiles), 2)
        if _cosine(profiles[a], profiles[b]) > TRIGRAM_SIMILARITY_CEILING
    ]
    assert not similar, f"cultures too alike: {similar}"


def test_person__family_member_shares_surname_but_not_known_as() -> None:
    book = _fresh_book()
    rng = WorldRng(11)
    father = book.person(rng, "highland", Gender.MALE)
    son = book.person(rng, "highland", Gender.MALE, family_of=father)
    assert son.last_name == father.last_name
    assert son.known_as != father.known_as
    assert son.known_as.endswith(father.surname_short)


def test_place__names_are_unique_and_pronounceable() -> None:
    book = _fresh_book()
    rng = WorldRng(12)
    places = [book.place(rng, "coastal") for _ in range(30)]
    assert len(places) == len(set(places))
    assert all(gates.is_pronounceable(place) for place in places)


def test_culture__unknown_key__raises() -> None:
    with pytest.raises(NameGenerationError, match="unknown name culture"):
        _fresh_book().culture("atlantis")


def _single_name_culture() -> NameCulture:
    return NameCulture.model_validate(
        {
            "kind": "region",
            "label": "Tiny",
            "onsets": {"k": 1},
            "nuclei": {"a": 1},
            "codas": {"": 1},
            "stress": "first",
            "given": {"syllables": {2: 1}, "male_endings": {"o": 1}, "female_endings": {"a": 1}},
            "surname": {
                "shapes": {"root_suffix": 1},
                "root_syllables": {1: 1},
                "suffixes": {"ven": 1},
            },
            "hyphen_share": 0.0,
            "diacritic_rate": 0.0,
        }
    )


def test_denylist__blocks_the_only_possible_name() -> None:
    # Canary: the grammar can only say "Kako Kaven"; denying it must exhaust the attempts.
    book = NameBook({"tiny": _single_name_culture()}, frozenset({"kaven"}), frozenset())
    with pytest.raises(NameGenerationError, match="no acceptable"):
        book.person(WorldRng(1), "tiny", Gender.MALE)


def test_blocklist__blocks_substrings() -> None:
    book = NameBook({"tiny": _single_name_culture()}, frozenset(), frozenset({"ven"}))
    with pytest.raises(NameGenerationError, match="no acceptable"):
        book.person(WorldRng(1), "tiny", Gender.MALE)


def test_book__single_name_grammar_still_yields_one_name_before_collision() -> None:
    book = NameBook({"tiny": _single_name_culture()}, frozenset(), frozenset())
    name = book.person(WorldRng(1), "tiny", Gender.MALE)
    assert name.known_as == "Kaven"


@pytest.mark.parametrize(
    ("component", "expected"),
    [
        ("Karven", True),
        ("Ka", False),
        ("Averyveryverylongname", False),
        ("Kaaan", False),
        ("Krstnbvk", False),
        ("Aeiouaeiou", False),
    ],
)
def test_is_pronounceable__table(component: str, expected: bool) -> None:
    assert gates.is_pronounceable(component) is expected


def test_plain__folds_diacritics_and_special_letters() -> None:
    assert plain("Ørsted-Šimák") == "orstedsimak"


def test_book__restore_undoes_a_discarded_attempt() -> None:
    book = _fresh_book()
    rng = WorldRng(13)
    saved = book.checkpoint()
    first = book.person(rng.fork("a"), "highland", Gender.MALE)
    book.restore(saved)
    again = book.person(rng.fork("a"), "highland", Gender.MALE)
    assert first == again
