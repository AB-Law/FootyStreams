"""The show chat model: failures of every kind become a ChatError (no network)."""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from email.message import Message

import pytest

from footystreams.cli.lm_chat import LmStudioChat
from footystreams.extensions.show.producer import ChatError


def test_chat__a_refused_connection_is_a_chat_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(ChatError, match="refused"):
        LmStudioChat().complete("system", "user")


def test_chat__an_http_error_carries_the_servers_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bad_request(*_a: object, **_k: object) -> None:
        raise urllib.error.HTTPError(
            "http://x", 400, "Bad Request", Message(), io.BytesIO(b"context length exceeded")
        )

    monkeypatch.setattr(urllib.request, "urlopen", bad_request)
    with pytest.raises(ChatError, match=r"400.*context length exceeded"):
        LmStudioChat().complete("system", "user")


def test_chat__a_timeout_is_a_chat_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(*_a: object, **_k: object) -> None:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(ChatError, match="timed out"):
        LmStudioChat().complete("system", "user")
