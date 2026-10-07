"""Plain-text league reports (pure): the table and each club's money."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.club import Club
from footystreams.domain.standings import StandingRow
from footystreams.domain.transfer import Transfer
from footystreams.domain.types import ClubId, PlayerId

MILLION = 1_000_000
NAME_WIDTH = 26
HEADER = (
    f"{'#':>2}  {'Club':<{NAME_WIDTH}} {'P':>3} {'W':>3} {'D':>3} {'L':>3} "
    f"{'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}"
)


def format_table(rows: Sequence[StandingRow], names: Mapping[ClubId, str]) -> str:
    """The league table, one club per line."""
    lines = [
        f"{row.position:>2}  {names[row.club_id]:<{NAME_WIDTH}} {row.played:>3} {row.won:>3} "
        f"{row.drawn:>3} {row.lost:>3} {row.goals_for:>4} {row.goals_against:>4} "
        f"{row.goal_difference:>+4} {row.points:>4}"
        for row in rows
    ]
    return "\n".join([HEADER, *lines])


def format_money(clubs: Sequence[Club], opening: Mapping[ClubId, int]) -> str:
    """Each club's balance and its change since ``opening``, in millions of crowns."""
    lines = [f"{'Club':<{NAME_WIDTH}} {'Balance':>10} {'Change':>10}"]
    for club in sorted(clubs, key=lambda item: item.id):
        balance = club.finances.balance
        change = balance - opening.get(club.id, balance)
        lines.append(
            f"{club.name:<{NAME_WIDTH}} {balance / MILLION:>9.1f}m {change / MILLION:>+9.1f}m"
        )
    return "\n".join(lines)


def format_transfers(
    transfers: Sequence[Transfer],
    names: Mapping[ClubId, str],
    players: Mapping[PlayerId, str],
) -> str:
    """Completed transfers, oldest first: date, player, from, to, fee in millions."""
    header = f"{'Date':<11} {'Player':<22} {'From':<{NAME_WIDTH}} {'To':<{NAME_WIDTH}} {'Fee':>8}"
    lines = [
        f"{t.completed_on.isoformat():<11} {players.get(t.player_id, t.player_id):<22} "
        f"{names.get(t.from_club_id, t.from_club_id):<{NAME_WIDTH}} "
        f"{names.get(t.to_club_id, t.to_club_id):<{NAME_WIDTH}} {t.fee / MILLION:>7.1f}m"
        for t in sorted(transfers, key=lambda item: (item.completed_on, item.id))
    ]
    return "\n".join([header, *lines])
