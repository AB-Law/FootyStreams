"""The show chat model over LM Studio: any failure becomes a ``ChatError`` (impure: network)."""

from __future__ import annotations

import urllib.error

from footystreams.cli.lm_client import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    ChatSettings,
    post_chat,
)
from footystreams.extensions.show.producer import ChatError


class LmStudioChat:
    """The show ``ChatModel``: any failure becomes a ``ChatError`` so the show can retry."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        temperature: float = 0.8,
        timeout_s: float = 300.0,
    ) -> None:
        """Configure the target; no connection is opened until the first request."""
        self.model = model
        self.endpoint = endpoint
        self.temperature = temperature
        self.timeout_s = timeout_s

    def complete(self, system: str, user: str) -> str:
        """Ask the model, or raise ``ChatError``."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        settings = ChatSettings(self.endpoint, self.model, self.temperature, self.timeout_s)
        try:
            return post_chat(settings, messages)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            msg = f"HTTP {error.code}: {detail}"
            raise ChatError(msg) from error
        except (OSError, TimeoutError, ValueError, TypeError) as error:
            msg = f"{type(error).__name__}: {error}"
            raise ChatError(msg) from error
