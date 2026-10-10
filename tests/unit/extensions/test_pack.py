"""BroadcastBrief packing stays inside the world's facts."""

from __future__ import annotations

from footystreams.extensions.pack import pack_broadcast_brief
from footystreams.extensions.template_narrator import TemplateNarrator
from footystreams.league.clock import read_date
from footystreams.league.friendly import build_friendly_setup
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import tables_from_catalog
from tests.factories.league_db import make_league_db
from tests.factories.league_run import make_engine
from tests.factories.world import make_world

WORLD = make_world(1)


def test_pack__resolves_wider_club_names_on_career_lines() -> None:
    factory = make_league_db(1)
    engine = make_engine(1)
    with factory() as uow:
        home, away = uow.clubs.all()[:2]
        setup = build_friendly_setup(uow, home.id, away.id, engine, read_date(uow))
    brief = pack_broadcast_brief(WORLD, setup)
    assert brief.home.name == home.name
    assert brief.away.name == away.name
    named = [
        line.club_name
        for person in brief.players
        for line in person.career
        if line.club_name is not None
    ]
    wider_names = {club.name for club in WORLD.wider_clubs}
    assert named
    assert set(named) <= wider_names


def test_pack__summary_fills_score_and_template_narrates() -> None:
    factory = make_league_db(1)
    engine = make_engine(1)
    with factory() as uow:
        home, away = uow.clubs.all()[:2]
        setup = build_friendly_setup(uow, home.id, away.id, engine, read_date(uow))
        referee = uow.referees.require(setup.referee_id)
        tables = tables_from_catalog(engine.tables.formations)
    result = run_match(setup, 2, SimConfig(), tables, referee)
    brief = pack_broadcast_brief(WORLD, setup, result.summary)
    assert brief.score is not None
    assert brief.score.home == result.summary.score_home
    lines = TemplateNarrator().narrate(brief, brief.crew)
    assert lines
    assert lines[0].beat == "intro"
    assert "Good evening" in lines[0].text
    assert sum(line.duration_ms for line in lines) >= 60_000
