"""Local-LLM Narrator via LM Studio's OpenAI-compatible HTTP API (impure; narrate CLI only)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

from footystreams.cli.lm_client import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_S,
    ChatSettings,
    post_chat,
)
from footystreams.extensions.brief import BroadcastBrief, CommentaryLine, CrewMember
from footystreams.extensions.template_narrator import TemplateNarrator

SYSTEM_PROMPT = (
    "You write a Valmere Premier League television news desk segment. "
    "Sound like a real sports news presenter: warm, clear, complete sentences, no slang dumps. "
    "Phrase ONLY the facts in the JSON brief. "
    "Do not invent clubs, scores, transfers, injuries, or people. "
    "Produce 10 to 14 lines covering: welcome, both clubs, both managers if present, "
    "two notable players, the result and key numbers, then a sign-off. "
    "Reply with a JSON array of objects: "
    '{"speaker_id","speaker_name","text","beat","duration_ms"}. '
    "beat must be one of intro, club_colour, player_focus, wrap. "
    "Each text 1-3 spoken sentences (about 180-420 characters). "
    "Set duration_ms between 10000 and 16000 so the segment runs about two to three minutes. "
    "Use the provided crew as speakers; alternate presenter and analysts."
)


class LMStudioNarrator:
    """Calls LM Studio chat completions; falls back to TemplateNarrator on any failure."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        """Configure the HTTP target; no connection is opened until narrate runs."""
        self.model = model
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self._fallback = TemplateNarrator()

    def narrate(
        self, brief: BroadcastBrief, speakers: tuple[CrewMember, ...]
    ) -> tuple[CommentaryLine, ...]:
        """Ask LM Studio for lines; return the template script if the call fails or is invalid."""
        cast = speakers or brief.crew
        try:
            raw = self._chat(brief, cast)
            lines = _parse_lines(raw, cast)
        except (
            OSError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return self._fallback.narrate(brief, cast)
        return lines or self._fallback.narrate(brief, cast)

    def _chat(self, brief: BroadcastBrief, cast: tuple[CrewMember, ...]) -> str:
        user_payload = {
            "brief": brief.model_dump(mode="json"),
            "speakers": [member.model_dump() for member in cast],
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        settings = ChatSettings(self.endpoint, self.model, timeout_s=self.timeout_s)
        return post_chat(settings, messages)


def _parse_lines(raw: str, cast: tuple[CrewMember, ...]) -> tuple[CommentaryLine, ...]:
    data = _load_json_payload(raw)
    rows = data if isinstance(data, list) else data.get("lines") or data.get("commentary")
    if not isinstance(rows, list):
        msg = "expected a JSON array of commentary lines"
        raise TypeError(msg)
    by_id = {member.id: member for member in cast}
    lines: list[CommentaryLine] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        line = _one_line(row, by_id, cast[0] if cast else None)
        if line is not None:
            lines.append(line)
    return tuple(lines)


def _load_json_payload(raw: str) -> Any:
    """Parse model output; tolerate a fenced ```json block if the model wraps it."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(inner).strip()
    return json.loads(text)


def _one_line(
    row: dict[str, Any],
    by_id: dict[str, CrewMember],
    default: CrewMember | None,
) -> CommentaryLine | None:
    text = str(row.get("text") or "").strip()
    if not text:
        return None
    speaker_id = str(row.get("speaker_id") or (default.id if default else ""))
    member = by_id.get(speaker_id, default)
    if member is None:
        return None
    beat = str(row.get("beat") or "club_colour")
    if beat not in {"intro", "club_colour", "player_focus", "wrap"}:
        beat = "club_colour"
    duration = row.get("duration_ms", 4000)
    try:
        duration_ms = int(duration)
    except (TypeError, ValueError):
        duration_ms = 4000
    duration_ms = max(500, min(60_000, duration_ms))
    return CommentaryLine(
        speaker_id=member.id,
        speaker_name=str(row.get("speaker_name") or member.known_as),
        text=text[:700],
        beat=beat,  # type: ignore[arg-type]
        duration_ms=duration_ms,
    )
