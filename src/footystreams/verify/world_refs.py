"""W01 foreign keys, W07 one squad per player, W08 contracts match squad entries."""

from __future__ import annotations

from collections import Counter

from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.types import EntityKind
from footystreams.domain.world import WIDER_WORLD_PREFIX, World
from footystreams.verify.violation import Violation

MIN_SHIRT, MAX_SHIRT = 1, 99


class Findings:
    """Collects violations of one check family; ``expect`` records one when a fact fails."""

    def __init__(self, code: str) -> None:
        """Start collecting violations that carry ``code``."""
        self.code = code
        self.problems: list[Violation] = []

    def expect(self, subject: str, message: str, *, holds: bool) -> None:
        """Record a violation about ``subject`` unless ``holds``."""
        if not holds:
            self.problems.append(Violation(self.code, message, subject))


def _known_club(club_id: str, clubs: set[str]) -> bool:
    return club_id in clubs or club_id.startswith(WIDER_WORLD_PREFIX)


def check_references(world: World) -> list[Violation]:
    """W01: every id a record points at exists (earlier employers outside the league excepted)."""
    clubs = {str(c.id) for c in world.clubs}
    nations = {str(n.id) for n in world.nations}
    findings = Findings("W01")
    for city in world.cities:
        findings.expect(
            city.id, f"nation {city.nation_id} does not exist", holds=city.nation_id in nations
        )
    for player in world.players:
        _player_references(findings, player, clubs, nations)
    _employment_references(findings, world, clubs)
    _club_references(findings, world, clubs, nations)
    _relationship_references(findings, world)
    return [*findings.problems, *_duplicate_ids(world)]


def _employment_references(findings: Findings, world: World, clubs: set[str]) -> None:
    for manager in world.managers:
        if manager.contract:
            club_id = manager.contract.club_id
            findings.expect(
                manager.id, f"contract club {club_id} does not exist", holds=club_id in clubs
            )
        for stint in manager.career_history:
            holds = _known_club(stint.club_id, clubs)
            findings.expect(manager.id, f"career club {stint.club_id} does not exist", holds=holds)
    for competition in world.competitions:
        for club_id in competition.club_ids:
            findings.expect(
                competition.id, f"club {club_id} does not exist", holds=club_id in clubs
            )
    for entry in world.ledger_opening:
        findings.expect(
            entry.id, f"ledger club {entry.club_id} does not exist", holds=entry.club_id in clubs
        )


def _player_references(
    findings: Findings, player: Player, clubs: set[str], nations: set[str]
) -> None:
    holds = player.nationality in nations
    findings.expect(player.id, f"nationality {player.nationality} does not exist", holds=holds)
    if player.contract:
        club_id = player.contract.club_id
        findings.expect(
            player.id, f"contract club {club_id} does not exist", holds=club_id in clubs
        )
    for stint in player.career_history:
        holds = _known_club(stint.club_id, clubs)
        findings.expect(player.id, f"career club {stint.club_id} does not exist", holds=holds)


def _club_references(findings: Findings, world: World, clubs: set[str], nations: set[str]) -> None:
    managers = {str(m.id) for m in world.managers}
    staff = {str(s.id): s for s in world.staff}
    players = {str(p.id): p for p in world.players}
    for club in world.clubs:
        nation = club.location.nation_id
        findings.expect(club.id, f"nation {nation} does not exist", holds=nation in nations)
        if club.manager_id is not None:
            findings.expect(
                club.id,
                f"manager {club.manager_id} does not exist",
                holds=club.manager_id in managers,
            )
        for staff_id in club.staff_ids:
            member = staff.get(staff_id)
            holds = member is not None and member.club_id == club.id
            findings.expect(club.id, f"staff {staff_id} is not employed by the club", holds=holds)
        for prospect_id in club.academy.prospect_ids:
            prospect = players.get(prospect_id)
            holds = prospect is not None and prospect.is_youth
            findings.expect(
                club.id, f"academy prospect {prospect_id} is not a youth player", holds=holds
            )
        for rivalry in club.rivalries:
            holds = rivalry.club_id in clubs and rivalry.club_id != club.id
            findings.expect(club.id, f"rivalry with {rivalry.club_id} is invalid", holds=holds)


def _relationship_references(findings: Findings, world: World) -> None:
    ids: dict[EntityKind, set[str]] = {
        EntityKind.PLAYER: {str(p.id) for p in world.players},
        EntityKind.MANAGER: {str(m.id) for m in world.managers},
        EntityKind.STAFF: {str(s.id) for s in world.staff},
        EntityKind.REFEREE: {str(r.id) for r in world.referees},
        EntityKind.MEDIA: {str(m.id) for m in world.media},
        EntityKind.CLUB: {str(c.id) for c in world.clubs},
    }
    for row in world.relationships:
        findings.expect(row.id, "relationship links an entity to itself", holds=row.a != row.b)
        for end in (row.a, row.b):
            holds = end.id in ids.get(end.kind, set())
            findings.expect(row.id, f"{end.kind.value} {end.id} does not exist", holds=holds)


def _duplicate_ids(world: World) -> list[Violation]:
    everyone = [
        *(str(p.id) for p in world.players),
        *(str(m.id) for m in world.managers),
        *(str(s.id) for s in world.staff),
        *(str(r.id) for r in world.referees),
        *(str(m.id) for m in world.media),
        *(str(c.id) for c in world.clubs),
    ]
    return [
        Violation("W01", "id is used twice", item) for item, n in Counter(everyone).items() if n > 1
    ]


def check_registration(world: World) -> list[Violation]:
    """W07 one squad per player, W08 contracts agree with squad entries and shirt numbers."""
    entries: dict[str, list[tuple[str, int]]] = {}
    for entry in world.squad_entries:
        entries.setdefault(str(entry.player_id), []).append(
            (str(entry.club_id), entry.squad_number)
        )
    findings = Findings("W07")
    problems: list[Violation] = []
    for player in world.players:
        found = entries.get(str(player.id), [])
        findings.expect(
            player.id, "player is registered with more than one squad", holds=len(found) <= 1
        )
        problems.extend(_contract_matches_entry(player, found))
    return [*findings.problems, *problems, *_shirt_numbers(world)]


def _contract_matches_entry(player: Player, found: list[tuple[str, int]]) -> list[Violation]:
    if player.contract is None:
        free = player.status is PlayerStatus.FREE_AGENT and not found
        return (
            []
            if free
            else [Violation("W08", "player without a contract is not a free agent", player.id)]
        )
    if len(found) != 1 or found[0][0] != player.contract.club_id:
        return [Violation("W08", "contract club and squad entry disagree", player.id)]
    if found[0][1] != player.squad_number:
        return [Violation("W08", "squad number differs from the squad entry", player.id)]
    if player.contract.end <= player.contract.start:
        return [Violation("W08", "contract ends before it starts", player.id)]
    return []


def _shirt_numbers(world: World) -> list[Violation]:
    numbers = Counter((str(e.club_id), e.squad_number) for e in world.squad_entries)
    findings = Findings("W08")
    for (club_id, number), count in numbers.items():
        findings.expect(
            club_id, f"shirt {number} is worn by more than one player", holds=count == 1
        )
        findings.expect(
            club_id,
            f"shirt {number} is outside {MIN_SHIRT}-{MAX_SHIRT}",
            holds=MIN_SHIRT <= number <= MAX_SHIRT,
        )
    return findings.problems
