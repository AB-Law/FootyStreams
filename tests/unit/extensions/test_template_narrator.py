"""Template desk script is longer and reads like a news segment."""

from __future__ import annotations

from footystreams.extensions.brief import (
    BroadcastBrief,
    ClubBrief,
    CrewMember,
    ScoreBrief,
)
from footystreams.extensions.template_narrator import TemplateNarrator


def test_template_narrator__produces_a_multi_minute_desk_script() -> None:
    brief = BroadcastBrief(
        match_id="mch_test",
        home=ClubBrief(
            id="clb_a",
            name="Seisund County",
            nickname="the Reds",
            short_code="SEI",
            founded_year=1871,
            city="Seisund",
            rivalry_label="city derby",
            rivalry_origin="A feud over a stolen cup.",
        ),
        away=ClubBrief(
            id="clb_b",
            name="Bukach Harriers",
            nickname="the Sparks",
            short_code="BUK",
            founded_year=1901,
            city="Bukach",
        ),
        score=ScoreBrief(home=2, away=2, ht_home=1, ht_away=1, potm_name="Svivinfell"),
        team_stats_note="shots 12-14, xG 1.16-1.57, possession 50%-50%",
        crew=(
            CrewMember(id="m1", known_as="Ann", role="presenter", catchphrases=("Stay with us.",)),
            CrewMember(id="m2", known_as="Bob", role="pundit"),
            CrewMember(id="m3", known_as="Cid", role="pundit"),
        ),
    )
    lines = TemplateNarrator().narrate(brief, brief.crew)
    assert len(lines) >= 5
    total_ms = sum(line.duration_ms for line in lines)
    assert total_ms >= 60_000
    assert "Good evening" in lines[0].text
    assert "Seisund County" in lines[0].text or "Seisund County" in lines[1].text
    assert "?" not in lines[-1].text or "VPL" in lines[-1].text
    assert all(len(line.text) > 40 for line in lines)
