"""Triggers to the running channel: breaking news cuts in, a guest joins after the current one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from footystreams.cli import channel as channel_module
from footystreams.cli.channel import Channel, ChannelConfig, Runtime
from footystreams.cli.channel_store import ChannelStore
from footystreams.extensions.show.models import Segment, SegmentKind
from footystreams.extensions.show.producer import ChatModel, Producer
from footystreams.extensions.show.triggers import Trigger
from tests.factories.show import EchoChat, FakeMatches, ScriptedChat, chat_error, newsroom


class Stage:
    """A fake clock that only moves when told to, and a log that remembers."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.logged: list[str] = []

    @property
    def runtime(self) -> Runtime:
        return Runtime(clock=lambda: self.now, sleep=self.sleep, log=self.logged.append)

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def channel(tmp_path: Path, stage: Stage, chat: ChatModel | None = None) -> Channel:
    producer = Producer(newsroom(), chat or EchoChat(), FakeMatches())
    config = ChannelConfig(ahead_s=600.0, lead_s=15.0, max_segments=4)
    return Channel(producer, ChannelStore(tmp_path), config, stage.runtime)


def on_air(tmp_path: Path, now: float) -> dict[str, float | str]:
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    return next(e for e in index["segments"] if e["air_at"] <= now < e["air_at"] + e["duration_s"])


def ids(tmp_path: Path) -> list[str]:
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    return [entry["id"] for entry in index["segments"]]


def test_breaking__cuts_in_on_what_is_on_air_and_moves_the_rest_back(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage)
    runner.run()
    before = {e.id: e for e in runner.index.segments}
    stage.now = before["seg_000001"].air_at + 20
    runner.store.write_trigger(Trigger(kind="breaking", text="Seisund County sack their manager"))
    runner.config = ChannelConfig(ahead_s=1.0, lead_s=15.0, max_segments=0)
    asked_at = stage.now

    runner._step()

    entries = {e.id: e for e in runner.index.segments}
    assert entries["seg_000001"].duration_s == 22.0
    flash, reaction = entries["seg_000005"], entries["seg_000006"]
    assert flash.air_at == asked_at + 2.0
    assert reaction.air_at == flash.air_at + flash.duration_s
    assert entries["seg_000002"].air_at == reaction.air_at + reaction.duration_s
    assert ids(tmp_path)[:2] == ["seg_000001", "seg_000005"]
    assert any("BREAKING NEWS" in line for line in stage.logged)
    assert runner.store.pending_triggers() == []
    segment = Segment.model_validate_json(
        (tmp_path / "seg_000006.json").read_text(encoding="utf-8")
    )
    assert segment.kind is SegmentKind.BREAKING


def test_breaking__with_the_model_away_the_flash_airs_alone(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage, ScriptedChat(chat_error("down")))
    runner.store.write_trigger(Trigger(kind="breaking", text="Something has happened"))
    runner.config = ChannelConfig(ahead_s=1.0, max_segments=0)

    runner._step()

    assert ids(tmp_path) == ["seg_000001"]
    assert any("nothing to say" in line for line in stage.logged)


def test_guest__joins_after_the_segment_on_air(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage)
    runner.run()
    first = runner.index.segments[0]
    stage.now = first.air_at + 5
    runner.store.write_trigger(Trigger(kind="guest", text="Jorsen"))
    runner.config = ChannelConfig(ahead_s=1.0, lead_s=15.0, max_segments=0)

    runner._step()

    entries = runner.index.segments
    assert entries[0].duration_s == first.duration_s
    assert entries[1].kind == "interview"
    assert entries[1].air_at == first.air_at + first.duration_s
    assert entries[1].guest
    assert any("joining the desk" in line for line in stage.logged)
    assert runner.bible.requests == ()


def test_guest__somebody_unknown_is_logged_and_nothing_changes(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage)
    runner.config = ChannelConfig(ahead_s=1.0, max_segments=0)
    runner.store.write_trigger(Trigger(kind="guest", text="Nobody Atall Exists"))

    runner._step()

    assert runner.bible.requests == ()
    assert any("nobody in this world matches" in line for line in stage.logged)


def test_guest__booked_even_if_the_model_is_away_and_aired_when_it_returns(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage, ScriptedChat(chat_error("down"), chat_error("down")))
    runner.config = ChannelConfig(ahead_s=1.0, max_segments=0)
    runner.store.write_trigger(Trigger(kind="guest", text="Jorsen"))

    runner._step()

    assert runner.bible.requests
    assert not (tmp_path / "index.json").exists()
    runner.producer.chat = EchoChat()
    runner.config = ChannelConfig(ahead_s=600.0, max_segments=1)
    runner.run()
    assert runner.index.segments[0].kind == "interview"
    assert not runner.bible.requests


def test_triggers__a_broken_file_is_logged_and_removed(tmp_path: Path) -> None:
    stage = Stage()
    runner = channel(tmp_path, stage)
    runner.config = ChannelConfig(ahead_s=1.0, max_segments=0)
    broken = tmp_path / "triggers" / "1.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")

    runner._step()

    assert not broken.exists()
    assert any("ignoring 1.json" in line for line in stage.logged)


def test_main__breaking_and_guest_leave_trigger_files_for_the_running_channel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert channel_module.main(["breaking", "--out", str(tmp_path), "Big", "news", "tonight"]) == 0
    assert channel_module.main(["guest", "--out", str(tmp_path), "Jorsen"]) == 0
    store = ChannelStore(tmp_path)
    triggers = [store.read_trigger(path) for path in store.pending_triggers()]
    assert [(t.kind, t.text) for t in triggers] == [
        ("breaking", "Big news tonight"),
        ("guest", "Jorsen"),
    ]
    assert "within a few seconds" in capsys.readouterr().out


def test_main__a_trigger_that_is_too_long_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert channel_module.main(["breaking", "--out", str(tmp_path), "x" * 500]) == 2
    assert "channel: error" in capsys.readouterr().err
    assert ChannelStore(tmp_path).pending_triggers() == []


def test_store__reset_also_clears_waiting_triggers(tmp_path: Path) -> None:
    store = ChannelStore(tmp_path)
    store.write_trigger(Trigger(kind="guest", text="Jorsen"))
    store.reset()
    assert store.pending_triggers() == []
