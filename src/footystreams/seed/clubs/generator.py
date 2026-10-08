"""Generate one complete club: identity, ground, money, people and default tactics."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.manager import Manager, ManagerStyle
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffMember
from footystreams.domain.types import ClubId, ManagerId, PlayerId, StaffId
from footystreams.domain.world import City, SquadEntry
from footystreams.seed.clubs.archetypes import ClubArchetype
from footystreams.seed.clubs.finance import make_finances, opening_entry
from footystreams.seed.clubs.identity import IdentityRegistry, make_identity
from footystreams.seed.clubs.organisation import (
    make_academy,
    make_board,
    make_culture,
    make_facilities,
)
from footystreams.seed.clubs.signing import (
    WageTarget,
    assign_numbers,
    scale_wages,
    sign_squad,
    squad_entries,
)
from footystreams.seed.clubs.squad import CalibrationTarget, SquadBrief, generate_squad
from footystreams.seed.clubs.stadium import StadiumSite, make_fanbase, make_stadium
from footystreams.seed.clubs.tactics import default_tactics
from footystreams.seed.managers.generator import ManagerSpec, generate_manager
from footystreams.seed.managers.staff import generate_backroom
from footystreams.seed.players.context import GenerationContext

MANAGER_MISMATCH_CHANCE = 0.20
MANAGER_QUALITY_SPREAD = 8
MANAGER_QUALITY_OFFSET = 8
DEFAULT_NOT_FOUND_STYLE = ManagerStyle.BALANCED


@dataclass(frozen=True, slots=True)
class ClubDraft:
    """A generated club with everything that belongs to it."""

    archetype_key: str
    club: Club
    players: tuple[Player, ...]
    manager: Manager
    staff: tuple[StaffMember, ...]
    squad_entries: tuple[SquadEntry, ...]
    ledger: tuple[LedgerEntry, ...]
    city: City
    team_rating_target: float
    annual_income: int


@dataclass(frozen=True, slots=True)
class ClubPlan:
    """Inputs that decide a club's place in the league before it is generated."""

    archetype_key: str
    archetype: ClubArchetype
    quality: float


def _style_for(rng: WorldRng, archetype: ClubArchetype) -> ManagerStyle:
    """The archetype's usual style; one club in five gets a deliberate mismatch for drama.

    An elite archetype lists the styles its mismatch may draw from: a title contender never gets a
    low-block manager (M8: the strongest club played defensively and lost its edge to tactics).
    """
    if rng.bernoulli(MANAGER_MISMATCH_CHANCE):
        allowed = archetype.mismatch_styles or tuple(style.value for style in ManagerStyle)
        return ManagerStyle(rng.choice(sorted(allowed)))
    return ManagerStyle(rng.choice_weighted(archetype.style_weights))


def _manager(
    ctx: GenerationContext, rng: WorldRng, plan: ClubPlan, club_id: ClubId, region: str
) -> Manager:
    style = _style_for(rng.fork("style"), plan.archetype)
    reputation = rng.randint(*plan.archetype.reputation)
    quality = round(plan.quality) - MANAGER_QUALITY_OFFSET + rng.randint(0, MANAGER_QUALITY_SPREAD)
    spec = ManagerSpec(club_id, style, quality, reputation, region)
    return generate_manager(spec, ctx, rng.fork("manager"))


def generate_club(
    ctx: GenerationContext,
    rng: WorldRng,
    plan: ClubPlan,
    remaining_cities: list[City],
    registry: IdentityRegistry,
) -> ClubDraft:
    """Build a club from its plan; takes its city out of ``remaining_cities``."""
    tables = ctx.tables.clubs
    archetype = plan.archetype
    identity = make_identity(rng.fork("identity"), tables, archetype, remaining_cities, registry)
    remaining_cities.remove(identity.city)
    club_id = ClubId(ctx.ids.next("club"))
    region = identity.city.region
    reputation = rng.fork("reputation").randint(*archetype.reputation)
    manager = _manager(ctx, rng.fork("coaching"), plan, club_id, region)
    tactics = default_tactics(manager, ctx.tables)
    brief = SquadBrief(club_id, region, reputation, archetype, tactics)
    target = CalibrationTarget(plan.quality, tables.league.calibration_tolerance)
    seniors, youth = generate_squad(ctx, rng.fork("squad"), brief, target)
    finances, income = make_finances(rng.fork("finance"), archetype, tables.sponsors, ctx.today)
    everyone = [*seniors, *youth]
    numbers = assign_numbers(everyone, tables.shirt_numbers)
    signed = sign_squad(everyone, club_id, numbers, rng.fork("contracts"), ctx.today)
    ratio = rng.fork("wage-ratio").uniform(*archetype.wage_ratio)
    signed = scale_wages(signed, WageTarget(finances.wage_budget_weekly, ratio))
    staff = generate_backroom(club_id, round(plan.quality), region, ctx, rng.fork("staff"))
    season_end = dt.date.fromisoformat(tables.league.season_end)
    club = Club(
        id=club_id,
        name=identity.name,
        short_name=identity.short_name,
        short_code=identity.short_code,
        nickname=identity.nickname,
        colours=identity.colours,
        crest_description=identity.crest_description,
        founded_year=identity.founded_year,
        location=identity.location,
        stadium=make_stadium(
            rng.fork("stadium"),
            archetype,
            StadiumSite(identity.city, ctx.names, tables.stadium_suffixes, reputation),
        ),
        fanbase=make_fanbase(rng.fork("fanbase"), archetype),
        finances=finances,
        facilities=make_facilities(rng.fork("facilities"), archetype),
        academy=make_academy(
            rng.fork("academy"),
            archetype,
            tuple(PlayerId(str(p.id)) for p in signed if p.is_youth),
        ),
        board=make_board(rng.fork("board"), archetype, season_end),
        club_reputation=reputation,
        prestige=max(0, reputation - rng.fork("prestige").randint(0, 10)),
        culture=make_culture(rng.fork("culture"), archetype),
        default_tactics=tactics,
        manager_id=ManagerId(str(manager.id)),
        staff_ids=tuple(StaffId(str(member.id)) for member in staff),
    )
    return ClubDraft(
        archetype_key=plan.archetype_key,
        club=club,
        players=tuple(signed),
        manager=manager,
        staff=staff,
        squad_entries=tuple(squad_entries(signed, club_id)),
        ledger=(opening_entry(ctx.ids, club_id, finances.balance, ctx.today),),
        city=identity.city,
        team_rating_target=plan.quality,
        annual_income=income,
    )
