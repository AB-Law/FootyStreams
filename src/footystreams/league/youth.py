"""Academy intake, youth contracts and promotion to the first team.

Generating a person needs names, geography and archetypes, which belong to the seed layer. The
league layer therefore describes who it wants as ``ProspectRequest``s (``domain.prospects``) and
receives players from a ``ProspectFactory`` that the composition root wires in.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.player import Player, PlayerStatus, SquadStatus
from footystreams.domain.prospects import ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Position
from footystreams.domain.valuation import market_value_of, wage_from_value
from footystreams.league.development_config import YouthConfig

NATURAL_POSITION_FLOOR = 85  # a first-team player is at home in his main position
MIN_INTAKE_ABILITY = 10
QUALITY_BASE, QUALITY_SPAN = 0.85, 0.3  # intake level runs 0.85-1.15 of the mean by academy quality
ABILITY_SPREAD = 0.35  # of the intake mean ability, in standard deviations
CONTRACT_END_MONTH_DAY = (6, 30)
MIN_TERM_DAYS = 90


def intake_requests(
    club: Club,
    shape: tuple[Sequence[Position], float],
    season_key: str,
    config: YouthConfig,
    rng: WorldRng,
) -> list[ProspectRequest]:
    """The year's academy intake for a club.

    ``shape`` is (the club's formation positions, the league's mean senior ability): positions are
    drawn from the formation so the intake mirrors what a team needs, and ability scales with the
    league level and the academy's quality.
    """
    positions, mean_ability = shape
    quality = club.academy.intake_quality
    bonus = config.potential_bonus_base + round(config.potential_bonus_per_quality * quality)
    requests = []
    for index in range(club.academy.intake_size):
        stream = rng.fork(f"intake:{index}")
        level = mean_ability * config.ability_fraction * (QUALITY_BASE + QUALITY_SPAN * quality)
        ability = max(MIN_INTAKE_ABILITY, round(level + stream.normal(0.0, level * ABILITY_SPREAD)))
        requests.append(
            ProspectRequest(
                key=f"{season_key}:{club.id}:{index}",
                position=stream.choice(list(positions)),
                age=stream.randint(*config.intake_age),
                ability=ability,
                potential_bonus=bonus,
                region=club.location.region,
                club_reputation=club.club_reputation,
                club_id=club.id,
                youth=True,
            )
        )
    return requests


def contract_end(today: dt.date, years: int) -> dt.date:
    """The 30 June ``years`` contract seasons after ``today``.

    The first season ends on the first 30 June at least ``MIN_TERM_DAYS`` away, so a deal signed
    just before the summer does not expire days later.
    """
    first = dt.date(today.year, *CONTRACT_END_MONTH_DAY)
    if (first - today).days < MIN_TERM_DAYS:
        first = first.replace(year=first.year + 1)
    return first.replace(year=first.year + years - 1)


def youth_contract(club_id: ClubId, today: dt.date, config: YouthConfig) -> Contract:
    """A youth deal: the configured wage, a prospect's squad role."""
    return Contract(
        club_id=club_id,
        start=today,
        end=contract_end(today, config.contract_years),
        wage_weekly=config.wage_weekly,
        squad_role=SquadRole.PROSPECT,
    )


def signed_prospect(player: Player, club_id: ClubId, today: dt.date, config: YouthConfig) -> Player:
    """A newly created prospect under his academy contract."""
    signed = player.model_copy(
        update={
            "contract": youth_contract(club_id, today, config),
            "squad_status": SquadStatus.YOUTH,
            "status": PlayerStatus.ACTIVE,
            "is_youth": True,
        }
    )
    return signed.model_copy(update={"market_value": market_value_of(signed, today)})


def promoted(player: Player, today: dt.date) -> Player:
    """The prospect moved up to the first team on a proper wage; revalidated as a senior."""
    competence = dict(player.position_competence)
    competence[player.primary_position] = max(
        competence[player.primary_position], NATURAL_POSITION_FLOOR
    )
    contract = player.contract
    wage = wage_from_value(market_value_of(player, today))
    senior = player.model_copy(
        update={
            "is_youth": False,
            "squad_status": SquadStatus.FIRST_TEAM,
            "position_competence": competence,
            "contract": contract.model_copy(
                update={
                    "wage_weekly": max(wage, contract.wage_weekly),
                    "squad_role": SquadRole.ROTATION,
                }
            )
            if contract
            else None,
        }
    )
    return Player.model_validate(senior.model_dump())
