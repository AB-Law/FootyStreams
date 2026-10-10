"""LM Studio response parsing (no network)."""

from __future__ import annotations

from footystreams.cli.lm_client import message_content
from footystreams.cli.lmstudio_narrator import _load_json_payload, _parse_lines
from footystreams.extensions.brief import CrewMember


def test_message_content__reads_openai_chat_shape() -> None:
    body = {"choices": [{"message": {"role": "assistant", "content": '[{"text":"Hi"}]'}}]}
    assert message_content(body) == '[{"text":"Hi"}]'


def test_load_json_payload__strips_fenced_block() -> None:
    raw = '```json\n[{"speaker_id":"a","speaker_name":"Ann","text":"Hello","beat":"intro"}]\n```'
    data = _load_json_payload(raw)
    assert isinstance(data, list)
    assert data[0]["text"] == "Hello"


def test_parse_lines__builds_commentary_from_array() -> None:
    cast = (CrewMember(id="a", known_as="Ann", role="presenter"),)
    raw = (
        '[{"speaker_id":"a","speaker_name":"Ann","text":"Hello desk",'
        '"beat":"intro","duration_ms":2000}]'
    )
    lines = _parse_lines(raw, cast)
    assert len(lines) == 1
    assert lines[0].text == "Hello desk"
    assert lines[0].beat == "intro"
