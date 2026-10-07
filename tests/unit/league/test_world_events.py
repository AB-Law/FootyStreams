from __future__ import annotations

from footystreams.domain.mood import ModifierVisibility
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.league.config import WorldEventsConfig
from footystreams.league.mood_config import MoodConfig
from footystreams.league.world_events import generate_life_events
from tests.factories.league_config import make_league_config, make_mood_config
from tests.factories.mood import TODAY
from tests.factories.world import make_world

CONFIGS = (make_league_config().world_events, make_mood_config())


def _players() -> list[Player]:
    return list(make_world(1).players)


def _hot(hazard: float) -> tuple[WorldEventsConfig, MoodConfig]:
    return (CONFIGS[0].model_copy(update={"daily_hazard": hazard}), CONFIGS[1])


def test_generate_life_events__certain_hazard__everyone_with_a_contract_gets_one() -> None:
    players = [p for p in _players() if p.contract]
    delta = generate_life_events(players, TODAY, WorldRng(1), _hot(3.0))
    assert len(delta.world_events) == len(players) == len(delta.modifiers)


def test_generate_life_events__zero_hazard__nothing_happens() -> None:
    assert generate_life_events(_players(), TODAY, WorldRng(1), _hot(0.0)).is_empty()


def test_generate_life_events__same_seed_and_day__same_delta() -> None:
    a = generate_life_events(_players(), TODAY, WorldRng(3), _hot(0.3))
    b = generate_life_events(list(reversed(_players())), TODAY, WorldRng(3), _hot(0.3))
    assert a.content_hash() == b.content_hash()


def test_generate_life_events__removing_a_player__does_not_change_the_others() -> None:
    players = _players()
    full = generate_life_events(players, TODAY, WorldRng(3), _hot(0.4))
    fewer = generate_life_events(players[1:], TODAY, WorldRng(3), _hot(0.4))
    rest = {m.id for m in fewer.modifiers}
    assert rest <= {m.id for m in full.modifiers}


def test_generate_life_events__each_modifier__cites_its_event_and_matches_its_visibility() -> None:
    delta = generate_life_events(_players(), TODAY, WorldRng(5), _hot(3.0))
    events = {e.id: e for e in delta.world_events}
    for modifier in delta.modifiers:
        assert modifier.source.world_event_id is not None
        event = events[modifier.source.world_event_id]
        assert event.visibility is modifier.visibility
    assert ModifierVisibility.PUBLIC in {e.visibility for e in events.values()}
