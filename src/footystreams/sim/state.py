"""Mutable match state: the only place in the simulation where objects are changed in place.

Hot-path data lives in `__slots__` dataclasses and plain floats (docs/design/11 section 6.2);
Pydantic is used only at the boundary where events are built. Everything here is owned by one
`simulate_match` call and never shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from footystreams.domain.injury import InjurySeverity
from footystreams.domain.match import TeamSheet
from footystreams.domain.types import PlayerId, Position, RoleId
from footystreams.sim.effective import Skills
from footystreams.sim.side import Side, opposite
from footystreams.sim.tables import Formation
from footystreams.sim.tactics_view import TacticsView
from footystreams.sim.weather import NEUTRAL, Conditions

REGULATION_PERIOD_S = 2700.0


class Line(IntEnum):
    """Which row of the team a player belongs to; indexes per-line tables."""

    KEEPER = 0
    DEFENCE = 1
    MIDFIELD = 2
    ATTACK = 3


_LINE_OF = {
    Position.GK: Line.KEEPER,
    Position.CB: Line.DEFENCE,
    Position.RB: Line.DEFENCE,
    Position.LB: Line.DEFENCE,
    Position.RWB: Line.DEFENCE,
    Position.LWB: Line.DEFENCE,
    Position.DM: Line.MIDFIELD,
    Position.CM: Line.MIDFIELD,
    Position.AM: Line.MIDFIELD,
    Position.RM: Line.MIDFIELD,
    Position.LM: Line.MIDFIELD,
    Position.RW: Line.ATTACK,
    Position.LW: Line.ATTACK,
    Position.SS: Line.ATTACK,
    Position.ST: Line.ATTACK,
}


@dataclass(slots=True)
class PlayerState:
    """One player on the pitch: identity, effective skills and live position (absolute)."""

    player_id: PlayerId
    side: Side
    slot: int
    position: Position
    line: Line
    role: RoleId
    skills: Skills
    base_x: float  # formation slot in the team's own frame
    base_y: float
    x: float
    y: float
    shirt: int | None = None
    yellow_cards: int = 0
    base_skills: Skills | None = None  # skills before fatigue; set when the sim builds the player
    exhaustion: float = 0.0
    drain: float = 0.0  # this player's share of the exhaustion rate (before team context)
    energy_step: int = 0  # exhaustion bucket the current `skills` were built for


@dataclass(slots=True)
class TeamState:
    """One side's live state."""

    side: Side
    sheet: TeamSheet
    formation: Formation
    view: TacticsView
    attack_dir: int
    players: list[PlayerState]
    score: int = 0
    sent_off: list[PlayerState] = field(default_factory=list)
    bench: list[PlayerId] = field(default_factory=list)
    substituted_off: list[PlayerState] = field(default_factory=list)  # replaced or injured off
    subs_used: int = 0
    windows_used: int = 0
    last_window_s: float = -1e9  # elapsed_s of the latest substitution window

    @property
    def keeper(self) -> PlayerState:
        """The goalkeeper on the pitch (the first goalkeeper, else the player in slot order 0)."""
        for candidate in self.players:
            if candidate.position is Position.GK:
                return candidate
        return self.players[0]

    def player(self, player_id: PlayerId) -> PlayerState:
        """Return the on-pitch player with this id."""
        for candidate in self.players:
            if candidate.player_id == player_id:
                return candidate
        msg = f"player {player_id} is not on the pitch for {self.sheet.club.id}"
        raise KeyError(msg)


@dataclass(frozen=True, slots=True)
class InjuryCase:
    """The true diagnosis of an in-match injury; the event shows only what a viewer could see."""

    player_id: PlayerId
    side: Side
    name: str
    body_part: str
    severity: InjurySeverity
    elapsed_s: float


@dataclass(slots=True)
class MatchState:
    """The whole live match: both teams, the clock, the ball and who has it."""

    home: TeamState
    away: TeamState
    carrier: PlayerState
    period: int = 1
    t_period: float = 0.0
    tick: int = 0
    ball_x: float = 0.5
    ball_y: float = 0.5
    chain: int = 0
    chain_started_at: float = 0.0
    played_before_s: float = 0.0  # regulation plus added time of the periods already played
    stoppage_s: float = 0.0  # dead time accumulated in the current period (goals, cards, ...)
    is_derby: bool = False
    attendance: int = 0
    conditions: Conditions = NEUTRAL
    assist_from: PlayerState | None = None  # passer of the last completed pass in this chain
    last_turnover_s: float = field(default=-1e9)  # elapsed_s of the latest change of possession
    injury_log: list[InjuryCase] = field(default_factory=list)

    def team(self, side: Side) -> TeamState:
        """Return the team on a side."""
        return self.home if side == "home" else self.away

    @property
    def elapsed_s(self) -> float:
        """Playing seconds since kick-off, counted across periods (half-time excluded)."""
        return self.played_before_s + self.t_period

    @property
    def attackers(self) -> TeamState:
        """The team currently in possession."""
        return self.team(self.carrier.side)

    @property
    def defenders(self) -> TeamState:
        """The team currently out of possession."""
        return self.team(opposite(self.carrier.side))


def line_of(position: Position) -> Line:
    """Return the row a position belongs to."""
    return _LINE_OF[position]
