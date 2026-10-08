import pytest
from pydantic import ValidationError

from footystreams.domain.types import FormationId, Position
from footystreams.sim.config import SimConfig, config_hash, merge_config
from footystreams.sim.tables import default_tables


def test_config_hash__is_stable_and_sixteen_hex_chars() -> None:
    assert config_hash(SimConfig()) == config_hash(SimConfig())
    assert len(config_hash(SimConfig())) == 16


def test_config_hash__changes_with_any_knob() -> None:
    assert config_hash(SimConfig()) != config_hash(SimConfig(home_advantage_scale=0.5))


def test_merge_config__applies_partial_overrides_and_validates() -> None:
    merged = merge_config(SimConfig(), {"emit_frames": True})
    assert merged.emit_frames is True
    assert merged.frame_interval_s == SimConfig().frame_interval_s


def test_merge_config__invalid_value__is_rejected() -> None:
    with pytest.raises(ValidationError):
        merge_config(SimConfig(), {"frame_interval_s": 0})


def test_merge_config__unknown_key__is_rejected() -> None:
    with pytest.raises(ValidationError):
        merge_config(SimConfig(), {"no_such_knob": 1})


def test_default_tables__ships_the_eight_standard_formations() -> None:
    assert sorted(default_tables().formations) == sorted(
        FormationId(name) for name in ("442", "433", "4231", "4141", "352", "532", "343", "4411")
    )


@pytest.mark.parametrize("formation", list(default_tables().formations.values()))
def test_formation__has_eleven_slots_goalkeeper_first_and_valid_coordinates(
    formation: object,
) -> None:
    slots = default_tables().formations[formation.formation_id].slots  # type: ignore[attr-defined]
    assert len(slots) == 11
    assert slots[0].position is Position.GK
    assert all(0.0 <= slot.x <= 1.0 and 0.0 <= slot.y <= 1.0 for slot in slots)
    assert [slot.position for slot in slots].count(Position.GK) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"shot": {"block_base": 0.5, "block_pressure": 0.4}},
        {"shot": {"off_target_min": 0.7}},
        {"shot": {"woodwork_share": 1.0}},
        {"passing": {"min_probability": 0.99, "max_probability": 0.5}},
        {"dribble": {"min_probability": 0.9, "max_probability": 0.1}},
        {"challenge": {"fail_intercept": 0.8, "fail_loose": 0.4}},
        {"tempo": {"noise": 1.0}},
        {"positioning": {"step_s": 0.0}},
        {"referee": {"call_scale": 0.0}},
        {"referee": {"consistency_noise": -0.1}},
        {"discipline": {"careless_max": 0.9, "reckless_max": 0.5}},
        {"discipline": {"red_threshold": 1.5}},
        {"discipline": {"card_s": -1.0}},
        {"restarts": {"overhit_min_m": 30.0, "overhit_max_m": 10.0}},
        {"restarts": {"direct_range_m": 0.0}},
        {"restarts": {"penalty_distance_m": 0.0}},
        {"restarts": {"corner_keeper_claim": 1.2}},
        {"offside": {"call_base": -0.1}},
        {"stoppage": {"first_half_min": 9, "first_half_max": 8}},
        {"stoppage": {"second_half_min": 11, "second_half_max": 10}},
    ],
)
def test_merge_config__values_the_simulator_cannot_divide_by_are_rejected(
    overrides: dict[str, dict[str, float]],
) -> None:
    with pytest.raises(ValidationError):
        merge_config(SimConfig(), overrides)
