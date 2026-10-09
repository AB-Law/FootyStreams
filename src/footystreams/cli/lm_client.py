"""A small client for LM Studio's OpenAI-compatible chat API (impure: network)."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "local-model"
DEFAULT_TIMEOUT_S = 90.0
DEFAULT_TEMPERATURE = 0.4
DEFAULT_MAX_TOKENS = 2_000


def message_content(body: object) -> str:
    """The assistant's text from a chat completions response body."""
    if not isinstance(body, dict):
        msg = "LM Studio response is not a JSON object"
        raise TypeError(msg)
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        msg = "LM Studio response has no choices"
        raise ValueError(msg)
    first = choices[0]
    if not isinstance(first, dict):
        msg = "LM Studio choice is not an object"
        raise TypeError(msg)
    message = first.get("message") or {}
    if not isinstance(message, dict):
        msg = "LM Studio message is not an object"
        raise TypeError(msg)
    content = message.get("content")
    if not isinstance(content, str):
        msg = "LM Studio message content is missing"
        raise TypeError(msg)
    return content


@dataclass(frozen=True, slots=True)
class ChatSettings:
    """Where to send a chat request and how."""

    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS
    # Reasoning models (qwen3.5 and friends) can spend the whole budget thinking and answer nothing.
    reasoning_effort: str | None = "none"


def post_chat(settings: ChatSettings, messages: list[dict[str, str]]) -> str:
    """Send one chat request and return the reply text; raises on any failure."""
    if not settings.endpoint.startswith(("http://", "https://")):
        msg = f"LM Studio endpoint must be http(s), got {settings.endpoint!r}"
        raise ValueError(msg)
    payload: dict[str, object] = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "messages": messages,
    }
    if settings.reasoning_effort is not None:
        payload["reasoning_effort"] = settings.reasoning_effort
    request = urllib.request.Request(  # noqa: S310
        settings.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.timeout_s) as response:  # noqa: S310
        body = json.loads(response.read().decode("utf-8"))
    content = message_content(body)
    if not content.strip():
        msg = "LM Studio returned an empty message (a reasoning model may have used up max_tokens)"
        raise ValueError(msg)
    return content
