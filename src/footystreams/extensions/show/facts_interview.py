"""Fact briefs for a guest on the desk: who they are, what they have done, how they talk."""

from __future__ import annotations

from pydantic import JsonValue

from footystreams.domain.club import Club
from footystreams.domain.person import Person
from footystreams.extensions.pack import manager_career_line, player_career_line
from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.facts import career_facts, standing_facts
from footystreams.extensions.show.ledger import scoreline
from footystreams.extensions.show.models import CastMember, GuestRef, Screen, ScreenRow
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.plan import Plan
from footystreams.extensions.show.segment_brief import SegmentBrief

NEUTRAL_KIT = ("#3a4a62", "#e8e8ee")


def _club_of(room: Newsroom, person_id: str) -> Club | None:
    if person_id in room.players:
        return room.clubs.get(room.club_of_player.get(person_id, ""))
    return next((c for c in room.clubs.values() if str(c.manager_id) == person_id), None)


def _personality(person: Person) -> dict[str, JsonValue]:
    traits = person.personality
    return {
        "interview_style": traits.interview_style,
        "humor_0_to_100": traits.humor,
        "ego_0_to_100": traits.ego,
        "sociability_0_to_100": traits.sociability,
        "media_openness_0_to_100": traits.media_openness,
        "professionalism_0_to_100": traits.professionalism,
    }


def _person(room: Newsroom, person_id: str) -> Person | None:
    return room.players.get(person_id) or room.managers.get(person_id)


def guest_ref(room: Newsroom, bible: ShowBible, person_id: str) -> GuestRef | None:
    """The guest as the viewer draws them: their own appearance, in their club's colours."""
    person = _person(room, person_id)
    if person is None:
        return None
    club = _club_of(room, person_id)
    is_player = person_id in room.players
    last = bible.results[-1] if bible.results else None
    if is_player and last is not None and last.potm_id == person_id:
        role = "Player of the match"
    else:
        role = f"{club.short_name} {'player' if is_player else 'manager'}" if club else "Guest"
    primary, secondary = (club.colours.primary, club.colours.secondary) if club else NEUTRAL_KIT
    return GuestRef(
        id=person_id,
        name=person.known_as,
        kind="player" if is_player else "manager",
        role=role[:40],
        appearance=dict(person.appearance.model_dump()),
        kit_primary=primary,
        kit_secondary=secondary,
    )


def guest_member(room: Newsroom, person_id: str) -> CastMember | None:
    """The guest as a speaker the model can write for."""
    person = _person(room, person_id)
    if person is None:
        return None
    city = room.cities.get(str(person.birthplace.city), str(person.birthplace.city))
    return CastMember(
        id=person_id,
        name=person.known_as,
        role="guest",
        humor=person.personality.humor,
        interview_style=person.personality.interview_style,
        birthplace=city,
    )


def _career(room: Newsroom, person_id: str) -> list[JsonValue]:
    if person_id in room.players:
        return career_facts(
            [player_career_line(s, room.wider) for s in room.players[person_id].career_history]
        )
    manager = room.managers[person_id]
    return career_facts([manager_career_line(s, room.wider) for s in manager.career_history])


def interview_brief(room: Newsroom, bible: ShowBible, plan: Plan) -> SegmentBrief | None:
    """A host interviews the guest; None if the guest is not someone in the world."""
    person_id = plan.subject
    guest = guest_ref(room, bible, person_id)
    person = _person(room, person_id)
    if guest is None or person is None:
        return None
    club = _club_of(room, person_id)
    last = bible.results[-1] if bible.results else None
    facts: dict[str, JsonValue] = {
        "guest": guest.name,
        "role": guest.role,
        "club": club.name if club else "",
        "age": person.age_on(bible.today),
        "career": _career(room, person_id),
        "personality": _personality(person),
        "on_the_desk": standing_facts(room, bible, str(club.id)) if club else {},
    }
    names = [guest.name, club.name if club else ""]
    names += [str(line["club"]) for line in facts["career"] if isinstance(line, dict)]  # type: ignore[union-attr]
    if last is not None and club is not None and str(club.id) in (last.home_id, last.away_id):
        facts["the_match_just_played"] = scoreline(last)
        facts["goals_in_it"] = sum(s.goals for s in last.scorers if s.player_id == person_id)
        names += [last.home_name, last.away_name]
    topics = (person_id, *([str(club.id)] if club else []))
    posted = not plan.off_rundown
    return SegmentBrief(
        title=f"Interview: {guest.name}",
        teaser="Post-match interview" if posted else f"Interview: {guest.name}",
        label="Interview",
        goal=(
            f"Interview {guest.name} ({guest.role}). One host asks, the others chip in, and "
            f"{guest.name} answers in the first person and in character: {_style(person)}. "
            "Keep to the facts: the guest can only talk about what is in them."
        ),
        facts=facts,
        names=tuple(name for name in names if name),
        topics=topics,
        screen=Screen(
            kind="card",
            title=guest.name.upper()[:40],
            rows=(
                ScreenRow(label="Role", value=guest.role[:20]),
                ScreenRow(label="Club", value=(club.short_name if club else "-")[:20]),
            ),
        ),
        guest=guest,
    )


def _style(person: Person) -> str:
    traits = person.personality
    return f"{traits.interview_style}, humor {traits.humor}/100, ego {traits.ego}/100"
