"""Breaking news: the hosts react to a headline someone has put out, and add nothing to it."""

from __future__ import annotations

import re

from pydantic import JsonValue

from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.reply import names_in
from footystreams.extensions.show.segment_brief import SegmentBrief
from footystreams.extensions.show.textutil import speakable

MAX_HEADLINE = 120


def clean_headline(text: str) -> str:
    """A headline the pixel font and the banner can show: plain, one line, not too long."""
    plain = speakable(re.sub(r"[\r\n]+", " ", text))
    return plain[:MAX_HEADLINE].rstrip()


def breaking_brief(room: Newsroom, headline: str) -> SegmentBrief:
    """The headline, and nothing else, for the hosts to react to."""
    facts: dict[str, JsonValue] = {"breaking_news_headline": headline}
    named = sorted(names_in(headline, room.vocabulary()))
    return SegmentBrief(
        title=f"Breaking: {headline}"[:80],
        teaser="Breaking news",
        label="Breaking news",
        goal=(
            f"BREAKING NEWS has just come in: {headline}. The hosts react live, in character: "
            "surprise, quick opinions, a joke if it fits, calling back to what they remember. "
            "They know only the headline: they must not add details, causes, quotes or numbers "
            "to it, and may say they are waiting for more."
        ),
        facts=facts,
        names=tuple(named),
        alert=headline,
    )
