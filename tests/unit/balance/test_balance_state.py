from __future__ import annotations

from pathlib import Path

import pytest

from footystreams.balance import state
from footystreams.balance.knobs import Knob
from footystreams.balance.sensitivity import Sensitivity

SETTINGS = {"matches": 120, "seed": 1, "metrics": ["goals_per_match"]}
HEADER = state.Header(SETTINGS, {"goals_per_match": 4.0}, {"goals_per_match": 0.5})


def test_state__a_written_file_is_read_back_with_its_header_and_finished_knobs(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sweep.jsonl"
    state.write_header(path, HEADER)
    state.append(path, Sensitivity(Knob("shot.xg_cap", 0.4), {"goals_per_match": 2.5}))
    state.append(path, Sensitivity(Knob("passing.base_back", 1.0), None))

    header, finished = state.load(path, SETTINGS)

    assert header == HEADER
    assert sorted(finished) == ["passing.base_back", "shot.xg_cap"]
    assert finished["shot.xg_cap"].effects == {"goals_per_match": 2.5}
    assert finished["passing.base_back"].effects is None
    assert finished["shot.xg_cap"].knob == Knob("shot.xg_cap", 0.4)


def test_state__resuming_with_different_settings_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "sweep.jsonl"
    state.write_header(path, HEADER)

    with pytest.raises(state.StateMismatchError, match="different settings"):
        state.load(path, {**SETTINGS, "matches": 240})


def test_state__a_header_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "sweep.jsonl"
    state.write_header(path, HEADER)

    with pytest.raises(FileExistsError):
        state.write_header(path, HEADER)


@pytest.mark.parametrize("content", ["", "{}\n", '{"knob": "a"}\n'])
def test_state__a_file_without_a_header_is_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "other.jsonl"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(state.StateMismatchError, match="not a balance state file"):
        state.load(path, SETTINGS)
