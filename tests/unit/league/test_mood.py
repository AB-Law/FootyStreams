from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from footystreams.domain.mood import DecayKind, ModifierVisibility, StateKind
from footystreams.domain.person import Personality
from footystreams.league.mood import active_modifiers, decay_factor, resolve_mood, sensitivity
from tests.factories.league_config import make_mood_config
from tests.factories.mood import TODAY, make_modifier
from tests.factories.person import make_personality
from tests.factories.strategies import personalities

CONFIG = make_mood_config()
EFFECT = CONFIG.kinds["personal_turmoil"]


def _days(count: int) -> dt.timedelta:
    return dt.timedelta(days=count)


def test_decay_factor__linear__falls_from_one_to_zero_over_the_span() -> None:
    modifier = make_modifier()
    assert decay_factor(modifier, EFFECT, TODAY) == 1.0
    assert decay_factor(modifier, EFFECT, TODAY + _days(10)) == 0.5
    assert decay_factor(modifier, EFFECT, TODAY + _days(20)) == 0.0


def test_decay_factor__before_start__is_zero() -> None:
    assert decay_factor(make_modifier(), EFFECT, TODAY - _days(1)) == 0.0


def test_decay_factor__half_life__halves_every_period() -> None:
    modifier = make_modifier(
        decay=DecayKind.HALF_LIFE, half_life_days=10, expires_on=TODAY + _days(100)
    )
    assert decay_factor(modifier, EFFECT, TODAY + _days(10)) == 0.5
    assert decay_factor(modifier, EFFECT, TODAY + _days(20)) == 0.25


def test_decay_factor__no_expiry__uses_the_kinds_default_days() -> None:
    modifier = make_modifier(expires_on=None)
    assert decay_factor(modifier, EFFECT, TODAY + _days(EFFECT.default_days)) == 0.0
    assert decay_factor(modifier, EFFECT, TODAY + _days(EFFECT.default_days // 3)) > 0.0


def test_sensitivity__resilient_player__feels_a_bad_episode_less() -> None:
    kind = StateKind.PERSONAL_TURMOIL
    tough = sensitivity(kind, EFFECT, make_personality(resilience=100), CONFIG)
    fragile = sensitivity(kind, EFFECT, make_personality(resilience=0), CONFIG)
    assert tough < 1.0 < fragile


def test_sensitivity__media_storm__media_open_player_feels_more() -> None:
    effect = CONFIG.kinds["media_storm"]
    open_ = sensitivity(StateKind.MEDIA_STORM, effect, make_personality(media_openness=100), CONFIG)
    shy = sensitivity(StateKind.MEDIA_STORM, effect, make_personality(media_openness=0), CONFIG)
    assert open_ > shy


def test_resolve_mood__no_modifiers__is_neutral() -> None:
    mood = resolve_mood(make_personality(), TODAY, [], CONFIG)
    assert (mood.mental_mult, mood.technical_mult, mood.physical_mult) == (1.0, 1.0, 1.0)
    assert mood.contributing_modifier_ids == ()


def test_resolve_mood__one_bad_episode__penalises_mental_most() -> None:
    mood = resolve_mood(make_personality(), TODAY, [make_modifier()], CONFIG)
    assert mood.mental_mult < mood.technical_mult < mood.physical_mult < 1.0
    assert mood.volatility_add > 0.0


def test_resolve_mood__good_episode__lifts_mental_most() -> None:
    modifier = make_modifier(kind=StateKind.DERBY_HERO)
    mood = resolve_mood(make_personality(), TODAY, [modifier], CONFIG)
    assert 1.0 < mood.technical_mult < mood.mental_mult


def test_resolve_mood__stacking__approaches_but_never_passes_the_cap() -> None:
    mods = [make_modifier(id=f"mod_{i:05d}", magnitude=1.0) for i in range(1, 8)]
    mood = resolve_mood(make_personality(resilience=0), TODAY, mods, CONFIG)
    assert mood.mental_mult >= 1.0 - CONFIG.caps.mental_penalty


def test_resolve_mood__private_modifier__is_not_a_public_storyline() -> None:
    private = make_modifier(visibility=ModifierVisibility.PRIVATE, summary_key="secret")
    public = make_modifier(id="mod_00002", summary_key="difficult_week")
    mood = resolve_mood(make_personality(), TODAY, [private, public], CONFIG)
    assert mood.public_storyline_keys == ("difficult_week",)
    assert set(mood.contributing_modifier_ids) == {"mod_00001", "mod_00002"}


def test_resolve_mood__order_of_modifiers__does_not_matter() -> None:
    a, b = make_modifier(), make_modifier(id="mod_00002", kind=StateKind.MEDIA_STORM)
    personality = make_personality()
    assert resolve_mood(personality, TODAY, [a, b], CONFIG) == resolve_mood(
        personality, TODAY, [b, a], CONFIG
    )


def test_active_modifiers__filters_not_started_and_expired() -> None:
    live = make_modifier()
    future = make_modifier(id="mod_00002", start_on=TODAY + _days(3), expires_on=TODAY + _days(9))
    expired = make_modifier(id="mod_00003", start_on=TODAY - _days(30), expires_on=TODAY)
    assert active_modifiers([live, future, expired], TODAY) == [live]


@given(
    personality=personalities(),
    kinds=st.lists(st.sampled_from(sorted(StateKind)), max_size=12),
    magnitudes=st.lists(st.floats(0.0, 1.0), min_size=12, max_size=12),
    offset=st.integers(0, 40),
)
def test_resolve_mood__any_modifier_set__stays_inside_the_hard_caps(
    personality: Personality, kinds: list[StateKind], magnitudes: list[float], offset: int
) -> None:
    mods = [
        make_modifier(
            id=f"mod_{i:05d}", kind=kind, magnitude=round(magnitudes[i], 4), expires_on=None
        )
        for i, kind in enumerate(kinds)
    ]
    mood = resolve_mood(personality, TODAY + _days(offset), mods, CONFIG)
    caps = CONFIG.caps
    assert 1 - caps.mental_penalty <= mood.mental_mult <= 1 + caps.mental_bonus
    assert 1 - caps.technical_penalty <= mood.technical_mult <= 1 + caps.technical_bonus
    assert 1 - caps.physical_penalty <= mood.physical_mult <= 1 + caps.physical_bonus
    assert 0.0 <= mood.volatility_add <= caps.volatility_add_max
