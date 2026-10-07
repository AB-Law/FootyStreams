"""Explicit catalogue of domain models that must declare ``__usage__``."""

from __future__ import annotations

from footystreams.domain.base import DomainModel
from footystreams.domain.club import Board, Club, Facilities, Fanbase, Rivalry, YouthAcademy
from footystreams.domain.competition import Competition, MatchRules, Season
from footystreams.domain.contract import Contract
from footystreams.domain.development import DevelopmentEntry, TrainingPlan
from footystreams.domain.finance import ClubFinances, LedgerEntry
from footystreams.domain.fixture import Fixture
from footystreams.domain.injury import Discipline, Injury, Suspension
from footystreams.domain.manager import Manager, Philosophy, SubHabits
from footystreams.domain.match import Match, MatchSetup, SetupRef, TeamSheet
from footystreams.domain.media import MediaPersonality, VoiceProfile
from footystreams.domain.memory import MemoryRecord
from footystreams.domain.mood import ResolvedMood, StateModifier, WorldEvent
from footystreams.domain.person import Appearance, Person, Personality
from footystreams.domain.player import Player
from footystreams.domain.proposals import Proposal
from footystreams.domain.referee import Referee
from footystreams.domain.relationship import Relationship
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.stadium import Pitch, Stadium
from footystreams.domain.staff import StaffMember
from footystreams.domain.standings import StandingRow
from footystreams.domain.tactics import TeamTactics
from footystreams.domain.transfer import Transfer, TransferBid, TransferWindow
from footystreams.domain.types import EntityRef, Pos
from footystreams.domain.weather import Weather

DOMAIN_MODELS: tuple[type[DomainModel], ...] = (
    Pos,
    EntityRef,
    Appearance,
    Personality,
    Person,
    Contract,
    Injury,
    Suspension,
    Discipline,
    Player,
    Manager,
    Philosophy,
    SubHabits,
    StaffMember,
    Referee,
    Pitch,
    Stadium,
    Fanbase,
    Facilities,
    YouthAcademy,
    Board,
    Rivalry,
    ClubFinances,
    LedgerEntry,
    Club,
    TeamTactics,
    Competition,
    MatchRules,
    Season,
    Fixture,
    StandingRow,
    ResolvedMood,
    StateModifier,
    WorldEvent,
    Weather,
    PlayerSnapshot,
    TeamSheet,
    MatchSetup,
    SetupRef,
    Match,
    Relationship,
    MemoryRecord,
    Proposal,
    TransferWindow,
    TransferBid,
    Transfer,
    TrainingPlan,
    DevelopmentEntry,
    VoiceProfile,
    MediaPersonality,
)
