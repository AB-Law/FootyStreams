"""L01-L06: a running league is consistent (money, results, schedule, squads, players, deals)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.match import Match, MatchStatus
from footystreams.domain.player import MAX_DEVELOPMENT_LOG, Player, PlayerStatus
from footystreams.domain.transfer import Transfer
from footystreams.domain.types import ClubId, Position
from footystreams.events.summary import MatchSummary
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings


def check_ledger(clubs: Sequence[Club], entries: Sequence[LedgerEntry]) -> list[Violation]:
    """L01: a club's balance equals its ledger sum; ledger entry ids are unique."""
    findings = Findings("L01")
    totals: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    for entry in entries:
        totals[str(entry.club_id)] += entry.amount
        findings.expect(entry.id, "ledger entry id appears twice", holds=entry.id not in seen)
        seen.add(entry.id)
    for club in clubs:
        balance, ledger = club.finances.balance, totals[str(club.id)]
        findings.expect(
            club.id,
            f"balance {balance} differs from the ledger sum {ledger}",
            holds=balance == ledger,
        )
    return findings.problems


def check_results(
    fixtures: Sequence[Fixture],
    matches: Sequence[Match],
    summaries: dict[str, MatchSummary],
) -> list[Violation]:
    """L02: every played fixture has one completed match whose score is the summary's."""
    findings = Findings("L02")
    by_fixture = {str(m.fixture_id): m for m in matches}
    for fixture in fixtures:
        match = by_fixture.get(fixture.id)
        played = fixture.status is FixtureStatus.PLAYED
        findings.expect(
            fixture.id, "played fixture has no match", holds=(match is not None) == played
        )
        if match is None:
            continue
        findings.expect(
            match.id,
            "match is not completed",
            holds=match.status is MatchStatus.COMPLETED,
        )
        findings.expect(
            match.id,
            "match clubs differ from the fixture's",
            holds=(match.home_club_id, match.away_club_id)
            == (fixture.home_club_id, fixture.away_club_id),
        )
        summary = summaries.get(match.id)
        findings.expect(match.id, "match has no stored summary", holds=summary is not None)
        if summary is not None:
            findings.expect(
                match.id,
                "match score differs from its summary",
                holds=(match.home_goals, match.away_goals)
                == (summary.score_home, summary.score_away),
            )
    return findings.problems


def check_season_complete(fixtures: Sequence[Fixture]) -> list[Violation]:
    """L03: when a season is over, every fixture was played."""
    findings = Findings("L03")
    for fixture in fixtures:
        findings.expect(
            fixture.id,
            f"fixture is {fixture.status.value}, not played",
            holds=fixture.status is FixtureStatus.PLAYED,
        )
    return findings.problems


@dataclass(frozen=True, slots=True)
class SquadRules:
    """The squad-size rules a league must keep (they come from the league configuration)."""

    min_senior: int
    max_senior: int
    min_goalkeepers: int


def check_squads(
    players: Sequence[Player], clubs: Sequence[ClubId], rules: SquadRules
) -> list[Violation]:
    """L04: every club has a legal number of senior players and enough goalkeepers."""
    findings = Findings("L04")
    seniors: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        if player.contract and not player.is_youth and player.status is PlayerStatus.ACTIVE:
            seniors[str(player.contract.club_id)].append(player)
    for club in clubs:
        squad = seniors[str(club)]
        findings.expect(
            club,
            f"{len(squad)} senior players, not {rules.min_senior}-{rules.max_senior}",
            holds=rules.min_senior <= len(squad) <= rules.max_senior,
        )
        keepers = sum(p.primary_position is Position.GK for p in squad)
        findings.expect(
            club,
            f"{keepers} goalkeepers, fewer than {rules.min_goalkeepers}",
            holds=keepers >= rules.min_goalkeepers,
        )
    return findings.problems


def check_development(players: Sequence[Player]) -> list[Violation]:
    """L05: ability never exceeds potential, the journal stays bounded, retirees have no club."""
    findings = Findings("L05")
    for player in players:
        findings.expect(
            player.id,
            f"ability {player.ability_current} exceeds potential {player.ability_potential}",
            holds=player.ability_current <= player.ability_potential,
        )
        findings.expect(
            player.id,
            f"development log has {len(player.development_log)} entries",
            holds=len(player.development_log) <= MAX_DEVELOPMENT_LOG,
        )
        findings.expect(
            player.id,
            "retired player still has a contract",
            holds=player.status is not PlayerStatus.RETIRED or player.contract is None,
        )
    return findings.problems


def check_transfers(
    transfers: Sequence[Transfer], entries: Sequence[LedgerEntry]
) -> list[Violation]:
    """L06: every paid transfer has a buyer leg and a seller leg, equal and opposite."""
    findings = Findings("L06")
    legs: dict[str, list[LedgerEntry]] = defaultdict(list)
    for entry in entries:
        if entry.ref.get("transfer_id"):
            legs[entry.ref["transfer_id"]].append(entry)
    known = {transfer.id for transfer in transfers}
    for transfer_id in legs:
        findings.expect(
            transfer_id,
            "orphan ledger legs with no matching transfer",
            holds=transfer_id in known,
        )
    for transfer in transfers:
        found = legs.get(transfer.id, [])
        if transfer.fee == 0:
            findings.expect(transfer.id, "a free transfer has ledger legs", holds=not found)
            continue
        buyer = [e for e in found if e.club_id == transfer.to_club_id and e.amount == -transfer.fee]
        seller = [
            e for e in found if e.club_id == transfer.from_club_id and e.amount == transfer.fee
        ]
        findings.expect(transfer.id, "the buyer's leg is missing or wrong", holds=len(buyer) == 1)
        findings.expect(transfer.id, "the seller's leg is missing or wrong", holds=len(seller) == 1)
        findings.expect(
            transfer.id, "the legs do not net to zero", holds=sum(e.amount for e in found) == 0
        )
    return findings.problems
