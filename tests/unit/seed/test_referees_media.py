from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

from footystreams.domain.media import MediaRole
from footystreams.domain.rng import WorldRng
from footystreams.seed.media import generate_crew
from footystreams.seed.media_tables import DISPOSITION_FIELDS, load_media_tables
from footystreams.seed.referees import REFEREE_COUNT, generate_referees
from footystreams.seed.static.files import StaticDataError
from tests.factories.world import make_generation_context

EXPECTED_ROLES = {
    MediaRole.LEAD_COMMENTATOR: 2,
    MediaRole.CO_COMMENTATOR: 2,
    MediaRole.REPORTER: 2,
    MediaRole.PRESENTER: 2,
    MediaRole.PUNDIT: 3,
}


def test_referees__ten_officials_with_the_planned_characters() -> None:
    officials = generate_referees(make_generation_context(), WorldRng(1))
    assert len(officials) == REFEREE_COUNT
    assert any(r.card_tendency >= 0.85 for r in officials)  # card-happy
    assert any(r.strictness <= 0.25 for r in officials)  # lenient old hand
    assert max(r.home_bias for r in officials) == pytest.approx(0.4)
    assert min(r.home_bias for r in officials) == pytest.approx(-0.1)


def test_referees__home_bias_averages_slightly_positive() -> None:
    officials = generate_referees(make_generation_context(), WorldRng(2))
    mean = sum(r.home_bias for r in officials) / len(officials)
    assert 0.05 <= mean <= 0.2


def test_referees__same_seed__identical() -> None:
    first = generate_referees(make_generation_context(), WorldRng(3))
    second = generate_referees(make_generation_context(), WorldRng(3))
    assert [r.model_dump_json() for r in first] == [r.model_dump_json() for r in second]


def test_referees__mixed_genders_and_unique_names() -> None:
    officials = generate_referees(make_generation_context(), WorldRng(4))
    assert len({r.gender for r in officials}) >= 2
    assert len({r.known_as for r in officials}) == REFEREE_COUNT


def test_crew__eleven_people_filling_every_role() -> None:
    crew = generate_crew(make_generation_context(), WorldRng(1))
    assert len(crew) == 11
    counts = {role: sum(m.role is role for m in crew) for role in MediaRole}
    assert counts == EXPECTED_ROLES


def test_crew__voice_ids_are_unique_placeholders() -> None:
    crew = generate_crew(make_generation_context(), WorldRng(1))
    voice_ids = [m.voice.bindings["placeholder"].voice_id for m in crew]
    assert len(voice_ids) == len(set(voice_ids))
    assert all(v.startswith("voice_placeholder_") for v in voice_ids)


def test_crew__personalities_are_pairwise_distinct() -> None:
    tables = make_generation_context().tables.media
    crew = generate_crew(make_generation_context(), WorldRng(5))
    for left, right in combinations(crew, 2):
        distance = (
            sum(
                (getattr(left.personality, f) - getattr(right.personality, f)) ** 2
                for f in DISPOSITION_FIELDS
            )
            ** 0.5
        )
        assert distance >= tables.distinctness_minimum


def test_crew__every_member_has_catchphrases_and_a_pronunciation_entry() -> None:
    crew = generate_crew(make_generation_context(), WorldRng(1))
    assert all(m.catchphrases and m.expertise_tags for m in crew)
    assert all(m.voice.lexicon[0].token == m.known_as for m in crew)


def test_crew__same_seed__identical() -> None:
    first = generate_crew(make_generation_context(), WorldRng(6))
    second = generate_crew(make_generation_context(), WorldRng(6))
    assert [m.model_dump_json() for m in first] == [m.model_dump_json() for m in second]


def test_media_tables__personality_with_missing_fields__rejected(tmp_path: Path) -> None:
    text = (
        "distinctness_minimum: 1\ncrew:\n  x:\n    role: pundit\n    summary: s\n"
        "    gender: {male: 1}\n    age: [30, 40]\n    personality: {ambition: 50}\n"
        "    voice: {age_range: mid, accent: a, timbre: [t], voice_register: mid,"
        " base_pace_wpm: 150, pace_variance: 0.1, energy_range: [0.2, 0.8], delivery_notes: n}\n"
        "    catchphrases: [c]\n    expertise: [e]\n    interjections: [i]\n"
    )
    (tmp_path / "media_archetypes.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(StaticDataError, match="exactly"):
        load_media_tables(tmp_path)
