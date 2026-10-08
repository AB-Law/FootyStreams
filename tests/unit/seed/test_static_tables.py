from __future__ import annotations

from pathlib import Path

import pytest

from footystreams.domain.injury import InjurySeverity
from footystreams.domain.types import Duty, Position
from footystreams.seed.static.files import StaticDataError, read_text_lines, read_yaml
from footystreams.seed.static.roles import ATTRIBUTE_NAMES, load_roles, role_id_for
from footystreams.seed.static.simple_tables import load_formations, load_injuries, load_traits


def _write(directory: Path, name: str, text: str) -> Path:
    (directory / name).write_text(text, encoding="utf-8")
    return directory


def test_load_formations__committed_table__has_valid_eleven_slot_shapes() -> None:
    catalog = load_formations()
    assert {"442", "433", "4231"} <= {str(key) for key in catalog.formations}
    assert all(len(formation.slots) == 11 for formation in catalog.formations.values())


def test_load_formations__bad_shape__names_the_formation(tmp_path: Path) -> None:
    text = "formations:\n  '442':\n    label: x\n    slots: [[GK, 0.1, 0.5]]\n"
    with pytest.raises(StaticDataError, match="formation '442'"):
        load_formations(_write(tmp_path, "formations.yaml", text))


def test_load_roles__every_position_has_a_role() -> None:
    catalog = load_roles()
    covered = {role.position for role in catalog.roles.values()}
    assert covered == set(Position)


def test_load_roles__multi_position_roles_expand_with_suffix() -> None:
    catalog = load_roles()
    assert role_id_for("full_back", Position.RB, multi_position=True) in catalog.roles
    assert role_id_for("poacher", Position.ST, multi_position=False) in catalog.roles
    assert "full_back" not in catalog.roles


def test_load_roles__duty_adjustments_change_weights() -> None:
    catalog = load_roles()
    central = catalog.roles[role_id_for("central_defender", Position.CB, multi_position=False)]
    defend = central.duties[Duty.DEFEND].attr_weights
    support = central.duties[Duty.SUPPORT].attr_weights
    assert defend["tackling"] > support["tackling"]


def test_load_roles__goalkeeper_ignores_duty_adjustments() -> None:
    catalog = load_roles()
    keeper = catalog.roles[role_id_for("goalkeeper", Position.GK, multi_position=False)]
    assert "tackling" not in keeper.duties[Duty.SUPPORT].attr_weights


def test_load_roles__all_weights_reference_known_attributes() -> None:
    catalog = load_roles()
    names = {
        name
        for role in catalog.roles.values()
        for spec in role.duties.values()
        for name in spec.attr_weights
    }
    assert names <= ATTRIBUTE_NAMES


def test_load_roles__unknown_attribute__rejected(tmp_path: Path) -> None:
    text = (
        "duty_profiles:\n  support: {}\n"
        "roles:\n  odd:\n    positions: [ST]\n    duties: [support]\n    weights: {telepathy: 3}\n"
    )
    with pytest.raises(StaticDataError, match="telepathy"):
        load_roles(_write(tmp_path, "roles.yaml", text))


def test_load_roles__undefined_duty__rejected(tmp_path: Path) -> None:
    text = (
        "duty_profiles:\n  support: {}\n"
        "roles:\n  odd:\n    positions: [ST]\n    duties: [attack]\n    weights: {finishing: 1}\n"
    )
    with pytest.raises(StaticDataError, match="undefined duty"):
        load_roles(_write(tmp_path, "roles.yaml", text))


def test_load_traits__committed_table__marks_simulated_and_reserved_traits() -> None:
    traits = load_traits().traits.values()
    usages = {trait.usage for trait in traits}
    assert usages == {"S", "R"}
    assert sum(trait.usage == "S" for trait in traits) >= 14


def test_load_injuries__every_severity_is_represented() -> None:
    catalog = load_injuries()
    assert all(catalog.of_severity(severity) for severity in InjurySeverity)


def test_load_injuries__severity_durations_grow() -> None:
    catalog = load_injuries()
    longest_knock = max(item.max_days for item in catalog.of_severity(InjurySeverity.KNOCK))
    shortest_severe = min(item.min_days for item in catalog.of_severity(InjurySeverity.SEVERE))
    assert longest_knock < shortest_severe


def test_load_injuries__missing_severity__rejected(tmp_path: Path) -> None:
    text = (
        "injuries:\n  bruise: {label: Bruise, body_part: shin, severity: knock,"
        " min_days: 0, max_days: 3, weight: 1.0}\n"
    )
    with pytest.raises(StaticDataError, match="no injury type for severity"):
        load_injuries(_write(tmp_path, "injuries.yaml", text))


def test_read_yaml__missing_file__names_the_path(tmp_path: Path) -> None:
    with pytest.raises(StaticDataError, match=r"nope\.yaml"):
        read_yaml("nope.yaml", tmp_path)


def test_read_yaml__non_mapping__rejected(tmp_path: Path) -> None:
    with pytest.raises(StaticDataError, match="mapping"):
        read_yaml("list.yaml", _write(tmp_path, "list.yaml", "- a\n- b\n"))


def test_read_text_lines__skips_comments_and_blanks(tmp_path: Path) -> None:
    directory = _write(tmp_path, "words.txt", "# comment\n\n alpha \nbeta\n")
    assert read_text_lines("words.txt", directory) == ("alpha", "beta")


def test_read_text_lines__missing_file__raises(tmp_path: Path) -> None:
    with pytest.raises(StaticDataError, match="cannot read"):
        read_text_lines("missing.txt", tmp_path)
