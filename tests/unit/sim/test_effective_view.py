import pytest

from footystreams.domain.tactics import Mentality
from footystreams.domain.types import Position, RoleId
from footystreams.sim.effective import (
    UPPER_BOUND,
    build_skills,
    day_form_multiplier,
    multipliers,
)
from footystreams.sim.rng import SimRng
from footystreams.sim.tactics_view import build_view
from tests.factories.match import make_player_snapshot, make_team_sheet

NEUTRAL_DAY = 1.0


def _skills(**overrides: object) -> object:
    snapshot = make_player_snapshot(**overrides)
    mult = multipliers(snapshot, Position.ST, RoleId("poacher"), NEUTRAL_DAY)
    return build_skills(snapshot, mult)


def test_skills__flat_fifty_player_in_best_position__is_close_to_base() -> None:
    skills = _skills(position_competence={Position.ST: 100})
    assert 47.0 < skills.finishing < 52.0  # type: ignore[attr-defined]


def test_skills__out_of_position__is_clearly_lower() -> None:
    in_position = _skills(position_competence={Position.ST: 100})
    out_of_position = _skills(position_competence={Position.ST: 0})
    assert out_of_position.finishing < 0.7 * in_position.finishing  # type: ignore[attr-defined]


def test_skills__never_exceed_the_upper_bound() -> None:
    snapshot = make_player_snapshot(form=1.0, morale=1.0, match_sharpness=1.0)
    mult = multipliers(snapshot, Position.ST, RoleId("poacher"), 1.07)
    assert build_skills(snapshot, mult).pace <= UPPER_BOUND * snapshot.physical.pace


def test_multipliers__good_form_beats_bad_form() -> None:
    good = multipliers(make_player_snapshot(form=1.0), Position.ST, RoleId("x"), NEUTRAL_DAY)
    bad = multipliers(make_player_snapshot(form=0.0), Position.ST, RoleId("x"), NEUTRAL_DAY)
    assert good.technical > bad.technical


def test_day_form__consistent_players_vary_less() -> None:
    steady = [day_form_multiplier(100, SimRng(seed)) for seed in range(200)]
    erratic = [day_form_multiplier(1, SimRng(seed)) for seed in range(200)]
    assert max(steady) - min(steady) < max(erratic) - min(erratic)


def test_day_form__consumes_exactly_one_gauss_draw() -> None:
    rng = SimRng(1)
    day_form_multiplier(50, rng)
    assert rng.draws == 4


def test_tactics_view__defaults_come_from_modules_and_mentality() -> None:
    view = build_view(make_team_sheet())
    assert view.mentality == 0.0
    assert view.press_intensity == pytest.approx(0.6)
    assert view.line_height == pytest.approx(0.5)


def test_tactics_view__mentality_scale_is_signed() -> None:
    sheet = make_team_sheet()
    attacking = sheet.model_copy(
        update={"tactics": sheet.tactics.model_copy(update={"mentality": Mentality.ALL_OUT})}
    )
    assert build_view(attacking).mentality == 1.0
