"""Deterministic template Narrator: a longer desk script phrased from BroadcastBrief facts only."""

from __future__ import annotations

from footystreams.extensions.brief import (
    BroadcastBrief,
    CareerLine,
    ClubBrief,
    CommentaryLine,
    CrewMember,
    ManagerBrief,
    PersonBrief,
    ScoreBrief,
)

# About 2-3 minutes when played back; each line is a spoken beat, not a caption flash.
INTRO_MS = 12_000
COLOUR_MS = 14_000
PLAYER_MS = 12_000
WRAP_MS = 14_000
# The desk may have a presenter and up to two analysts; the third crew member (index 2) is optional.
SECOND_ANALYST_INDEX = 2
EN_DASH = "\N{EN DASH}"


class TemplateNarrator:
    """Fallback narrator that never invents; safe when no local LLM is available."""

    def narrate(
        self, brief: BroadcastBrief, speakers: tuple[CrewMember, ...]
    ) -> tuple[CommentaryLine, ...]:
        """Build a full desk segment from the packed facts."""
        cast = speakers or brief.crew
        if not cast:
            return ()
        presenter = cast[0]
        analyst = cast[1] if len(cast) > 1 else cast[0]
        second = cast[SECOND_ANALYST_INDEX] if len(cast) > SECOND_ANALYST_INDEX else analyst
        lines: list[CommentaryLine] = [
            _line(presenter, _open(brief), "intro", INTRO_MS),
            _line(analyst, _home_club(brief.home), "club_colour", COLOUR_MS),
            _line(second, _away_club(brief.away), "club_colour", COLOUR_MS),
        ]
        if brief.home_manager is not None:
            lines.append(
                _line(
                    analyst, _manager(brief.home_manager, brief.home.name), "club_colour", COLOUR_MS
                )
            )
        if brief.away_manager is not None:
            lines.append(
                _line(
                    second, _manager(brief.away_manager, brief.away.name), "club_colour", COLOUR_MS
                )
            )
        for player in _pick_players(brief.players):
            speaker = analyst if player.side == "home" else second
            lines.append(_line(speaker, _player(player), "player_focus", PLAYER_MS))
        if brief.score is not None:
            lines.append(_line(presenter, _result(brief, brief.score), "wrap", WRAP_MS))
        lines.append(_line(presenter, _close(brief, presenter), "wrap", WRAP_MS))
        return tuple(lines)


def _line(speaker: CrewMember, text: str, beat: str, duration_ms: int) -> CommentaryLine:
    return CommentaryLine(
        speaker_id=speaker.id,
        speaker_name=speaker.known_as,
        text=text,
        beat=beat,  # type: ignore[arg-type]
        duration_ms=duration_ms,
    )


def _open(brief: BroadcastBrief) -> str:
    if brief.score is None:
        return (
            f"Good evening, and welcome to VPL News. "
            f"On the desk tonight we look ahead to {brief.home.name} against {brief.away.name}."
        )
    score = brief.score
    return (
        f"Good evening from the VPL News desk. "
        f"Full time: {brief.home.name} {score.home}, {brief.away.name} {score.away}. "
        f"Let's walk through what decided it."
    )


def _home_club(club: ClubBrief) -> str:
    text = (
        f"{club.name}, known as {club.nickname}, were founded in {club.founded_year} "
        f"and call {club.city} home."
    )
    if club.rivalry_label and club.rivalry_origin:
        text += f" Their {club.rivalry_label} still carries weight: {club.rivalry_origin}."
    elif club.rivalry_label:
        text += f" Tonight that {club.rivalry_label} was never far away."
    return text


def _away_club(club: ClubBrief) -> str:
    return (
        f"Opposite them, {club.name} — {club.nickname} — "
        f"out of {club.city}, a club dating back to {club.founded_year}."
    )


def _manager(manager: ManagerBrief, club_name: str) -> str:
    career = _career_phrase(manager.career)
    text = (
        f"{manager.known_as} took {club_name} with a {manager.style.replace('_', ' ')} approach, "
        f"and he is typically {_press_phrase(manager.press_tone)} in front of the cameras."
    )
    if career:
        text += f" Before this job he spent {career}."
    return text


def _press_phrase(tone: str) -> str:
    mapping = {
        "calm": "measured",
        "defensive": "guarded",
        "combative": "combative",
        "humorous": "light with a joke",
        "blunt": "blunt",
        "evasive": "careful not to give much away",
    }
    return mapping.get(tone, tone.replace("_", " "))


def _player(player: PersonBrief) -> str:
    age = f", aged {player.age}," if player.age is not None else ""
    text = f"One name to watch was {player.known_as}{age} operating as {player.role}."
    career = _career_phrase(player.career)
    if career:
        text += f" He arrived here after {career}."
    if player.storyline_keys:
        text += f" There has been talk around him lately: {', '.join(player.storyline_keys)}."
    return text


def _result(brief: BroadcastBrief, score: ScoreBrief) -> str:
    parts = [
        f"On the numbers, {brief.home.name} had {brief.team_stats_note}."
        if brief.team_stats_note
        else f"The scoreboard finished {score.home}{EN_DASH}{score.away}."
    ]
    if score.ht_home or score.ht_away:
        parts.append(f"It was {score.ht_home}{EN_DASH}{score.ht_away} at the break.")
    if score.potm_name:
        parts.append(f"Player of the match: {score.potm_name}.")
    return " ".join(parts)


def _close(brief: BroadcastBrief, presenter: CrewMember) -> str:
    if presenter.catchphrases:
        phrase = presenter.catchphrases[0].rstrip(".")
        catch = f' As {presenter.known_as} likes to say, "{phrase}."'
    else:
        catch = ""
    return (
        f"That wraps the desk for {brief.home.short_code} against {brief.away.short_code}. "
        f"More from VPL News after the break.{catch}"
    )


def _pick_players(players: tuple[PersonBrief, ...]) -> tuple[PersonBrief, ...]:
    home = [player for player in players if player.side == "home"]
    away = [player for player in players if player.side == "away"]
    chosen: list[PersonBrief] = []
    for side in (home, away):
        if not side:
            continue
        with_career = next((player for player in side if player.career), None)
        chosen.append(with_career if with_career is not None else side[0])
    return tuple(chosen)


def _career_phrase(lines: tuple[CareerLine, ...]) -> str:
    named = [line for line in lines if line.club_name]
    if not named:
        return ""
    first = named[0]
    years = max(1, first.to_year - first.from_year)
    seasons = "season" if years == 1 else "seasons"
    return f"{years} {seasons} at {first.club_name} ({first.detail})"
