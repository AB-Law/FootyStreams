"""What a match does to a player's body, form, morale, record and availability (pure)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.injury import Discipline, Injury, Suspension
from footystreams.domain.player import MAX_FORM_HISTORY, CareerStint, Player
from footystreams.events.summary import PlayerMatchStats
from footystreams.league.config import RecoveryConfig
from footystreams.league.outcome import Outcome

RATING_FLOOR = 3.0
RATING_SPAN = 7.0  # ratings run 3-10
MORALE_REASON = "result"


@dataclass(frozen=True, slots=True)
class PlayedMatch:
    """One player's match: his stats, how his side did and any injury he picked up."""

    stats: PlayerMatchStats
    outcome: Outcome
    injury: Injury | None


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _form(player: Player, rating: float, config: RecoveryConfig) -> tuple[float, tuple[float, ...]]:
    """Exponential moving average of the 0-1 form with the latest match rating."""
    latest = (rating - RATING_FLOOR) / RATING_SPAN
    weight = config.form_weight_new_rating
    history = (*player.form_history, round(latest, 4))[-MAX_FORM_HISTORY:]
    return _clamp((1 - weight) * player.form + weight * latest), history


def _morale(player: Player, outcome: Outcome, config: RecoveryConfig) -> float:
    shift = {Outcome.WIN: config.morale_win, Outcome.LOSS: config.morale_loss}.get(outcome, 0.0)
    return _clamp(player.morale + shift)


def _discipline(
    player: Player, stats: PlayerMatchStats, config: RecoveryConfig
) -> tuple[Discipline, Suspension | None]:
    """Season card tally and the ban a red card or a fifth yellow earns."""
    old = player.discipline
    yellows = old.yellows_season + stats.yellows
    threshold = config.suspension_yellow_threshold
    discipline = Discipline(
        yellows_season=yellows,
        reds_season=old.reds_season + stats.reds,
        yellow_ban_threshold_progress=yellows % threshold,
    )
    if stats.reds:
        return discipline, Suspension(
            matches_remaining=config.red_card_ban_matches, reason="red card"
        )
    if yellows // threshold > old.yellows_season // threshold:
        return discipline, Suspension(matches_remaining=1, reason="accumulated yellow cards")
    return discipline, player.suspension


def _career(player: Player, stats: PlayerMatchStats, today: dt.date) -> tuple[CareerStint, ...]:
    """Add the appearance and goals to the open spell; open one at his club if there is none."""
    history = list(player.career_history)
    for index in range(len(history) - 1, -1, -1):
        stint = history[index]
        if stint.to_date is None:
            history[index] = stint.model_copy(
                update={"apps": stint.apps + 1, "goals": stint.goals + stats.goals}
            )
            return tuple(history)
    if player.contract is None:
        return tuple(history)
    start = min(player.contract.start, today)
    history.append(
        CareerStint(club_id=player.contract.club_id, from_date=start, apps=1, goals=stats.goals)
    )
    return tuple(history)


def apply_match(
    player: Player, played: PlayedMatch, context: tuple[RecoveryConfig, dt.date]
) -> Player:
    """The player after playing: tired, sharper, new form and morale, cards, record, injury."""
    config, today = context
    stats = played.stats
    form, history = _form(player, stats.rating, config)
    discipline, suspension = _discipline(player, stats, config)
    return player.model_copy(
        update={
            "fatigue": _clamp(player.fatigue + stats.minutes * config.fatigue_per_match_minute),
            "match_sharpness": _clamp(player.match_sharpness + config.sharpness_gain_per_match),
            "form": form,
            "form_history": history,
            "morale": _morale(player, played.outcome, config),
            "discipline": discipline,
            "suspension": suspension,
            "career_history": _career(player, stats, today),
            "current_injury": played.injury or player.current_injury,
        }
    )


def serve_suspension(player: Player) -> Player:
    """One match of a ban served by a player who sat it out."""
    ban = player.suspension
    if ban is None:
        return player
    remaining = ban.matches_remaining - 1
    served = Suspension(matches_remaining=remaining, reason=ban.reason) if remaining else None
    return player.model_copy(update={"suspension": served})
