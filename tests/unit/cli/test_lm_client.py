"""The LM Studio client: request shape and how failures become a ChatError (no network)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from footystreams.cli.lm_client import ChatSettings, message_content, post_chat


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def reply(content: str) -> FakeResponse:
    return FakeResponse(json.dumps({"choices": [{"message": {"content": content}}]}).encode())


def test_post_chat__sends_the_model_messages_and_reasoning_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: dict[str, Any] = {}

    def fake_open(request: Any, timeout: float) -> FakeResponse:
        sent["body"] = json.loads(request.data)
        sent["timeout"] = timeout
        return reply("hello")

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    text = post_chat(ChatSettings(model="m", timeout_s=7.0), [{"role": "user", "content": "hi"}])
    assert text == "hello"
    assert sent["body"]["model"] == "m"
    assert sent["body"]["reasoning_effort"] == "none"
    assert sent["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert sent["timeout"] == 7.0


def test_post_chat__leaves_out_the_reasoning_setting_when_none_is_wanted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, Any]] = []

    def fake_open(request: Any, timeout: float) -> FakeResponse:
        seen.append(json.loads(request.data))
        return reply("x")

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    post_chat(ChatSettings(reasoning_effort=None), [])
    assert "reasoning_effort" not in seen[0]


def test_post_chat__refuses_an_endpoint_that_is_not_http() -> None:
    with pytest.raises(ValueError, match="http"):
        post_chat(ChatSettings(endpoint="file:///etc/passwd"), [])


def test_post_chat__an_empty_answer_is_an_error_with_a_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: reply("  "))
    with pytest.raises(ValueError, match="max_tokens"):
        post_chat(ChatSettings(), [])


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"choices": []},
        {"choices": [1]},
        {"choices": [{"message": 1}]},
        {"choices": [{"message": {}}]},
    ],
)
def test_message_content__rejects_bodies_that_are_not_chat_replies(body: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        message_content(body)
