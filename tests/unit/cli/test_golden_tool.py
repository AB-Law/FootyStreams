import json
from collections.abc import Callable
from pathlib import Path

import pytest

from footystreams.cli import golden
from footystreams.cli.golden import differences, load_golden, update
from footystreams.domain.versions import SIM_VERSION


def _doc(version: str = "9.9.9", digest: str = "a") -> dict[str, object]:
    return {"sim_version": version, "config_hash": "c", "cases": {"x": {"digest": digest}}}


def _returning(document: dict[str, object]) -> Callable[[], dict[str, object]]:
    return lambda: document


def test_differences__nothing_stored_means_everything_differs() -> None:
    assert differences(_doc(), None) == ["golden file missing"]


def test_differences__names_changed_cases_and_config_hash() -> None:
    stored = _doc()
    current = {**_doc(digest="b"), "config_hash": "d"}
    assert differences(current, stored) == ["config_hash", "x"]


def test_differences__identical_documents_have_no_differences() -> None:
    assert differences(_doc(), _doc()) == []


def test_load_golden__missing_file_is_none(tmp_path: Path) -> None:
    assert load_golden(tmp_path / "nope.json") is None


def test_update__refuses_when_output_changed_without_a_version_bump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "digests.json"
    path.write_text(json.dumps(_doc(version=SIM_VERSION, digest="old")), encoding="utf-8")
    monkeypatch.setattr(golden, "compute_golden", lambda: _doc(version=SIM_VERSION, digest="new"))
    assert update(path) == golden.EXIT_NEEDS_BUMP
    assert "bump it" in capsys.readouterr().err
    assert json.loads(path.read_text(encoding="utf-8"))["cases"]["x"]["digest"] == "old"


def test_update__writes_when_the_version_was_bumped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "digests.json"
    path.write_text(json.dumps(_doc(version="0.0.1", digest="old")), encoding="utf-8")
    monkeypatch.setattr(golden, "compute_golden", lambda: _doc(version=SIM_VERSION, digest="new"))
    assert update(path) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["cases"]["x"]["digest"] == "new"


def test_update__first_run_creates_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "sub" / "digests.json"
    monkeypatch.setattr(golden, "compute_golden", _returning(_doc()))
    assert update(path) == 0
    assert path.is_file()


def test_update__no_change_does_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "digests.json"
    path.write_text(json.dumps(_doc()), encoding="utf-8")
    monkeypatch.setattr(golden, "compute_golden", _returning(_doc()))
    assert update(path) == 0


def test_check__reports_mismatch_and_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "digests.json"
    path.write_text(json.dumps(_doc(digest="old")), encoding="utf-8")
    monkeypatch.setattr(golden, "compute_golden", _returning(_doc(digest="new")))
    assert golden.check(path) == golden.EXIT_STALE
    monkeypatch.setattr(golden, "compute_golden", _returning(_doc(digest="old")))
    assert golden.check(path) == 0
