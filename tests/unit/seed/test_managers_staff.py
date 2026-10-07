from __future__ import annotations

from pathlib import Path

import pytest

from footystreams.domain.manager import Manager, ManagerStyle
from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffRole
from footystreams.domain.types import ClubId, FormationId
from footystreams.seed.managers.generator import ManagerSpec, generate_manager
from footystreams.seed.managers.staff import BACKROOM, ROLE_FOCUS, generate_backroom
from footystreams.seed.managers.styles import load_styles
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.static.presets import load_presets
from footystreams.seed.static.tables import load_static_tables
from tests.factories.world import make_generation_context

CLUB = ClubId("clb_00001")


def _manager(style: ManagerStyle, seed: int = 1, *, club: ClubId | None = CLUB) -> Manager:
    ctx = make_generation_context()
    spec = ManagerSpec(club_id=club, style=style, quality=65, reputation=60, region="coastal")
    return generate_manager(spec, ctx, WorldRng(seed))


def test_presets__one_valid_preset_per_style_with_matching_slot_positions() -> None:
    tables = load_static_tables()
    assert set(tables.presets) == set(ManagerStyle)
    for preset in tables.presets.values():
        formation = tables.formations.formations[preset.tactics.formation]
        for slot, shape in zip(preset.tactics.slots, formation.slots, strict=True):
            assert tables.roles.roles[slot.role].position is shape.position


def test_presets__unusable_role__names_preset_and_slot(tmp_path: Path) -> None:
    tables = load_static_tables()
    text = (
        "presets:\n  p:\n    style: balanced\n    formation: '442'\n    mentality: balanced\n"
        "    slots: [" + ", ".join(['"poacher:attack"'] * 11) + "]\n    modules: {}\n"
    )
    (tmp_path / "tactic_presets.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(StaticDataError, match=r"preset 'p' slot 0"):
        load_presets(tables.roles, tables.formations, tmp_path)


def test_styles__every_style_has_a_prototype_and_preset_key() -> None:
    styles = load_styles()
    assert set(styles.styles) == set(ManagerStyle)


@pytest.mark.parametrize("style", list(ManagerStyle))
def test_generate_manager__valid_for_every_style(style: ManagerStyle) -> None:
    manager = _manager(style)
    assert manager.style is style
    assert manager.preferred_formation in manager.formation_proficiency
    assert len(manager.fallback_formations) <= 3
    assert manager.preferred_formation not in manager.fallback_formations
    assert 38 <= manager.age_on(make_generation_context().today) <= 66


def test_generate_manager__proficiency_tapers_from_preferred_to_others() -> None:
    manager = _manager(ManagerStyle.POSSESSION)
    preferred = manager.formation_proficiency[manager.preferred_formation]
    others = [
        value
        for key, value in manager.formation_proficiency.items()
        if key != manager.preferred_formation and key not in manager.fallback_formations
    ]
    assert others
    assert preferred > max(others)


def test_generate_manager__style_shapes_philosophy() -> None:
    gegen = [_manager(ManagerStyle.GEGEN_PRESS, seed=i) for i in range(12)]
    low = [_manager(ManagerStyle.LOW_BLOCK, seed=i) for i in range(12)]
    gegen_press = sum(m.philosophy.pressing_intensity for m in gegen) / 12
    low_press = sum(m.philosophy.pressing_intensity for m in low) / 12
    assert gegen_press > low_press + 0.4


def test_generate_manager__employed_has_contract_unemployed_does_not() -> None:
    assert _manager(ManagerStyle.BALANCED).contract is not None
    assert _manager(ManagerStyle.BALANCED, club=None).contract is None


def test_generate_manager__career_history_adds_up() -> None:
    manager = _manager(ManagerStyle.DIRECT)
    assert 2 <= len(manager.career_history) <= 4
    for stint in manager.career_history:
        assert stint.won + stint.drawn + stint.lost == stint.played


def test_generate_manager__same_seed__identical() -> None:
    assert (
        _manager(ManagerStyle.WING_PLAY, 4).model_dump_json()
        == _manager(ManagerStyle.WING_PLAY, 4).model_dump_json()
    )


def test_generate_manager__formations_come_from_the_style() -> None:
    styles = load_styles()
    manager = _manager(ManagerStyle.LOW_BLOCK)
    allowed = {FormationId(key) for key in styles.styles[ManagerStyle.LOW_BLOCK].formations}
    assert {manager.preferred_formation, *manager.fallback_formations} <= allowed


def test_backroom__standard_team_of_nine_with_role_shaped_attributes() -> None:
    ctx = make_generation_context()
    staff = generate_backroom(CLUB, 60, "coastal", ctx, WorldRng(2))
    assert len(staff) == sum(BACKROOM.values()) == 9
    assert all(member.club_id == CLUB for member in staff)
    physios = [m for m in staff if m.role is StaffRole.PHYSIO]
    scouts = [m for m in staff if m.role is StaffRole.SCOUT]
    assert min(p.attrs.injury_treatment for p in physios) > max(
        s.attrs.injury_treatment for s in scouts
    )
    assert set(ROLE_FOCUS) >= set(BACKROOM)


def test_backroom__known_as_values_are_unique_across_club_and_world() -> None:
    ctx = make_generation_context()
    first = generate_backroom(CLUB, 60, "coastal", ctx, WorldRng(2))
    second = generate_backroom(ClubId("clb_00002"), 60, "highland", ctx, WorldRng(3))
    names = [m.known_as for m in (*first, *second)]
    assert len(names) == len(set(names))
