"""The channel loop: it keeps the queue full, survives the model going away and resumes."""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

from footystreams.cli import channel as channel_module
from footystreams.cli.channel import Channel, ChannelConfig, Runtime
from footystreams.cli.channel_store import ChannelStore, atomic_write
from footystreams.extensions.show.feed import scheduled_end
from footystreams.extensions.show.producer import Producer
from footystreams.seed.world_io import write_world
from tests.factories.show import EchoChat, FakeMatches, ScriptedChat, chat_error, newsroom
from tests.factories.world import make_world


class Stage:
    """A fake clock that only moves when the loop sleeps, and a log that remembers."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.slept: list[float] = []
        self.logged: list[str] = []

    @property
    def runtime(self) -> Runtime:
        return Runtime(clock=lambda: self.now, sleep=self.sleep, log=self.logged.append)

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def channel(tmp_path: Path, stage: Stage, chat: object | None = None, **config: object) -> Channel:
    producer = Producer(newsroom(), chat or EchoChat(), FakeMatches())  # type: ignore[arg-type]
    settings = ChannelConfig(**{"ahead_s": 600.0, "lead_s": 15.0, "max_segments": 3, **config})  # type: ignore[arg-type]
    return Channel(producer, ChannelStore(tmp_path), settings, stage.runtime)


def test_channel__writes_segments_the_index_and_the_bible(tmp_path: Path) -> None:
    stage = Stage()
    assert channel(tmp_path, stage).run() == 0
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in index["segments"]] == [
        "seg_000001",
        "seg_000002",
        "seg_000003",
    ]
    for entry in index["segments"]:
        assert (tmp_path / entry["file"]).is_file()
    assert (tmp_path / "bible.json").is_file()
    for entry in index["segments"]:
        assert json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))["ticker"]
    assert len(index["cast"]) == 3


def test_channel__segments_are_scheduled_back_to_back_from_just_after_now(tmp_path: Path) -> None:
    stage = Stage()
    channel(tmp_path, stage).run()
    entries = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["segments"]
    assert entries[0]["air_at"] == stage.now + 15.0
    for before, after in pairwise(entries):
        assert after["air_at"] == before["air_at"] + before["duration_s"]


def test_channel__waits_while_enough_airtime_is_queued(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage, ahead_s=60.0, max_segments=2)
    runner.run()
    assert stage.slept, "it never waited although the queue was already full"
    assert scheduled_end(runner.index) - stage.now >= 0


def test_channel__a_silent_model_means_waiting_and_trying_again_with_a_growing_pause(
    tmp_path: Path,
) -> None:
    stage = Stage()
    good = EchoChat()

    class Outage:
        def __init__(self) -> None:
            self.refusals = 2

        def complete(self, system: str, user: str) -> str:
            if self.refusals:
                self.refusals -= 1
                raise chat_error("connection refused")
            return good.complete(system, user)

    channel(tmp_path, stage, Outage(), max_segments=1).run()
    assert stage.slept[:2] == [5.0, 10.0]
    assert any("not answering" in line for line in stage.logged)
    assert (tmp_path / "seg_000001.json").is_file()


def test_channel__resumes_after_a_restart_with_the_same_memory(tmp_path: Path) -> None:
    stage = Stage()
    channel(tmp_path, stage, max_segments=2).run()
    before = ChannelStore(tmp_path).load_bible()
    assert before is not None
    again = channel(tmp_path, stage, max_segments=1)
    assert again.bible == before
    again.run()
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in index["segments"]][-1] == "seg_000003"


def test_channel__a_segment_that_keeps_failing_is_skipped_not_retried_for_ever(
    tmp_path: Path,
) -> None:
    stage = Stage()
    junk = ScriptedChat(*["not json"] * 9)
    runner = channel(tmp_path, stage, junk, max_segments=0)
    for _ in range(3):
        runner._step()
    assert runner.bible.segment_count == 1
    assert runner.bible.failures == 0
    assert (tmp_path / "bible.json").is_file()


def test_atomic_write__leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "file.json"
    atomic_write(target, "{}")
    atomic_write(target, '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert [path.name for path in target.parent.iterdir()] == ["file.json"]


def test_store__reset_forgets_everything(tmp_path: Path) -> None:
    store = ChannelStore(tmp_path)
    channel(tmp_path, Stage(), max_segments=1).run()
    store.reset()
    assert store.load_bible() is None
    assert list(tmp_path.glob("*.json")) == []


def test_main__runs_a_finite_show_from_a_world_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_world(make_world(1), tmp_path / "world")
    monkeypatch.setattr(channel_module, "LmStudioChat", lambda *_a, **_k: EchoChat())
    monkeypatch.setattr(channel_module, "WorldMatches", lambda _world: FakeMatches())

    out = str(tmp_path / "feed")
    arguments = ["--world", str(tmp_path / "world"), "--out", out, "--max-segments", "2"]
    code = channel_module.main([*arguments, "--ahead-minutes", "30", "--reset"])

    assert code == 0
    assert (tmp_path / "feed" / "index.json").is_file()
    assert (tmp_path / "feed" / "seg_000002.json").is_file()
    assert "on air" in capsys.readouterr().out


def test_main__a_missing_world_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = channel_module.main(["--world", str(tmp_path / "nowhere"), "--max-segments", "1"])
    assert code == 2
    assert "channel: error" in capsys.readouterr().err


def test_parser__defaults_run_forever_with_ten_minutes_queued() -> None:
    arguments = channel_module.build_parser().parse_args([])
    assert arguments.max_segments is None
    assert arguments.ahead_minutes == 10.0
    assert arguments.reset is False
