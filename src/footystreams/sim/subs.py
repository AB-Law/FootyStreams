"""Substitution mechanics: who may come on, the window rules, and the change itself.

A team has `max_subs` changes in at most `max_windows` stoppages, plus half-time; an injury may
force a change beyond the window limit while changes remain. Substituted players never return.
The bench keeps its goalkeeper for a goalkeeper's replacement: outfield changes never use one
(docs/design/02 section 7). The AI that decides *when* to change is in `manager_ai.py`.
"""

from __future__ import annotations

from enum import StrEnum

from footystreams.domain.match import LineupSlot
from footystreams.domain.types import Duty, PlayerId, Position
from footystreams.events.discipline import SubstitutionEvent
from footystreams.sim.build import build_player
from footystreams.sim.config_manager import ManagerConfig
from footystreams.sim.emit import Meta
from footystreams.sim.play import Play, actor, label
from footystreams.sim.state import PlayerState, TeamState
from footystreams.sim.tables import FormationSlot

KEEPER_COMPETENCE = 80  # competence at goalkeeper above which a bench player counts as a keeper


class Window(StrEnum):
    """In which stoppage a change is made; it decides which limit applies."""

    PLAY = "play"
    HALFTIME = "halftime"
    FORCED = "forced"  # an injury forces it: exempt from the window limit


def is_keeper(team: TeamState, player_id: PlayerId) -> bool:
    """True when a squad member is a goalkeeper by competence."""
    snapshot = team.sheet.squad[player_id]
    return snapshot.position_competence.get(Position.GK, 0) >= KEEPER_COMPETENCE


def can_change(team: TeamState, now_s: float, window: Window, cfg: ManagerConfig) -> bool:
    """True when the team may make a change now under the substitution rules."""
    if team.subs_used >= cfg.max_subs or not team.bench:
        return False
    if window is not Window.PLAY:
        return True
    in_open_window = now_s - team.last_window_s <= cfg.window_gap_s
    return in_open_window or team.windows_used < cfg.max_windows


def replacement_for(team: TeamState, off: PlayerState) -> PlayerId | None:
    """Pick the bench player best suited to take `off`'s slot, or None if nobody fits the rules.

    A goalkeeper is replaced by a keeper when the bench has one; any other change never uses a
    bench keeper. Otherwise the best position competence wins (ties go to bench order).
    """
    keeper_off = off.position is Position.GK
    pool = [pid for pid in team.bench if is_keeper(team, pid) == keeper_off]
    if not pool:
        pool = list(team.bench) if keeper_off else []
    if not pool:
        return None
    return max(
        pool,
        key=lambda pid: (
            team.sheet.squad[pid].position_competence.get(off.position, 0),
            -team.bench.index(pid),
        ),
    )


def _register_window(team: TeamState, now_s: float, window: Window, cfg: ManagerConfig) -> None:
    """Count a new window when a play-time change opens one."""
    if window is Window.PLAY and now_s - team.last_window_s > cfg.window_gap_s:
        team.windows_used += 1
        team.last_window_s = now_s


def make_substitution(
    play: Play, off: PlayerState, on_id: PlayerId, reason: str, window: Window
) -> float:
    """Replace `off` with the bench player `on_id` in his slot; return the stoppage seconds."""
    state, cfg = play.state, play.cfg.manager
    team = state.team(off.side)
    _register_window(team, state.elapsed_s, window, cfg)
    entry = LineupSlot(slot=off.slot, player_id=on_id, role=off.role, duty=Duty.SUPPORT)
    spot = FormationSlot(off.position, off.base_x, off.base_y)
    newcomer = build_player(off.side, team.sheet, spot, entry, play.build)
    newcomer.x, newcomer.y = off.x, off.y
    team.players[team.players.index(off)] = newcomer
    team.bench.remove(on_id)
    team.substituted_off.append(off)
    team.subs_used += 1
    if state.carrier is off:
        state.carrier = newcomer
    if state.assist_from is off:
        state.assist_from = None
    meta = Meta(
        team=off.side,
        participants=(actor(off, "off"), actor(newcomer, "on")),
        pos=(off.x, off.y),
        headline=f"{label(team, on_id)} on for {label(team, off.player_id)}",
    )
    play.emit.emit(
        state,
        SubstitutionEvent,
        meta,
        player_off_id=off.player_id,
        player_on_id=on_id,
        reason=reason,
    )
    seconds = cfg.sub_s + cfg.sub_spread_s * (play.setpiece.u() - 0.5) * 2.0
    state.stoppage_s += seconds
    return seconds
