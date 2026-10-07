"""Invariants about who is on the pitch and how many changes were made (M06, M08).

M06 at most 11 per side are on the pitch, every substitution takes a player who is on it and
    brings one from the unused bench
M08 a side makes at most `subs_max` changes in at most `sub_windows` stoppages (injury changes
    and changes at the break do not need a window)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from footystreams.domain.competition import MatchRules
from footystreams.domain.match import MatchSetup, TeamSheet
from footystreams.events.clock import match_elapsed_s
from footystreams.events.discipline import SubstitutionEvent
from footystreams.events.types import MatchEvent
from footystreams.verify.discipline import TEAM_SIZE, leaver_at
from footystreams.verify.violation import Violation

SAME_WINDOW_S = 60  # lenient: changes this close are one stoppage, so the check never over-counts
HALF_MINUTES = 45


def _sheets(setup: MatchSetup) -> dict[str, TeamSheet]:
    return {"home": setup.home, "away": setup.away}


def check_pitch_state(events: Sequence[MatchEvent], setup: MatchSetup) -> list[Violation]:
    """M06: no side exceeds eleven and every change is legal."""
    found: list[Violation] = []
    on = {side: {slot.player_id for slot in sheet.lineup} for side, sheet in _sheets(setup).items()}
    bench = {side: set(sheet.bench) for side, sheet in _sheets(setup).items()}
    for position, event in enumerate(events):
        if event.team not in on:
            continue
        if isinstance(event, SubstitutionEvent):
            if event.player_off_id not in on[event.team]:
                found.append(Violation("M06", "player taken off is not on the pitch", event.id))
            if event.player_on_id not in bench[event.team]:
                found.append(Violation("M06", "player brought on is not an unused sub", event.id))
            on[event.team].discard(event.player_off_id)
            bench[event.team].discard(event.player_on_id)
            on[event.team].add(event.player_on_id)
        leaver = leaver_at(events, position)
        if leaver is not None:
            on[event.team].discard(leaver)
        if len(on[event.team]) > TEAM_SIZE:
            found.append(Violation("M06", f"{len(on[event.team])} players on the pitch", event.id))
    return found


def _needs_window(event: SubstitutionEvent) -> bool:
    """Injury changes and changes at the break are exempt from the window limit."""
    at_break = event.clock.period == 1 and event.clock.minute >= HALF_MINUTES
    return event.reason != "injury" and not at_break


def _window_count(times: list[int]) -> int:
    count, last = 0, None
    for moment in sorted(times):
        if last is None or moment - last > SAME_WINDOW_S:
            count += 1
        last = moment
    return count


def check_substitution_limits(
    events: Sequence[MatchEvent], rules: MatchRules | None = None
) -> list[Violation]:
    """M08: changes and substitution windows per side stay within the competition rules."""
    rules = rules or MatchRules()
    changes: dict[str, list[SubstitutionEvent]] = defaultdict(list)
    for event in events:
        if isinstance(event, SubstitutionEvent):
            changes[event.team].append(event)
    found: list[Violation] = []
    for team, made in sorted(changes.items()):
        if len(made) > rules.subs_max:
            found.append(Violation("M08", f"{team} made {len(made)} changes", made[-1].id))
        windows = _window_count([match_elapsed_s(e.clock) for e in made if _needs_window(e)])
        if windows > rules.sub_windows:
            found.append(Violation("M08", f"{team} used {windows} windows", made[-1].id))
    return found
