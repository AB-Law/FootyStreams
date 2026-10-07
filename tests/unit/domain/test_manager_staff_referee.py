"""Smoke tests for manager, staff and referee models."""

from __future__ import annotations

from typing import Any

from footystreams.domain.manager import (
    Manager,
    ManagerStyle,
    PressTone,
    TouchlineBehaviour,
)
from footystreams.domain.referee import Referee
from footystreams.domain.staff import StaffAttrs, StaffMember, StaffRole
from footystreams.domain.types import ClubId, FormationId
from tests.factories.person import make_person


def _with_person(extra: dict[str, Any]) -> dict[str, Any]:
    payload = make_person().model_dump()
    payload.update(extra)
    return payload


def test_manager__round_trip() -> None:
    manager = Manager.model_validate(
        _with_person(
            {
                "id": "mgr_test0001",
                "style": ManagerStyle.BALANCED,
                "philosophy": {
                    "possession_preference": 0.5,
                    "directness": 0.4,
                    "pressing_intensity": 0.5,
                    "tempo": 0.5,
                    "width": 0.5,
                    "defensive_line": 0.5,
                    "risk_taking": 0.5,
                },
                "preferred_formation": "433",
                "flexibility": 0.5,
                "substitution_habits": {
                    "earliest_minute": 55,
                    "aggressiveness": 0.5,
                    "fresh_legs_bias": 0.5,
                    "protect_lead_bias": 0.5,
                    "chase_game_bias": 0.5,
                    "reacts_to_cards": 0.5,
                },
                "touchline_behaviour": TouchlineBehaviour.CALM,
                "attributes": {
                    "tactical_knowledge": 70,
                    "man_management": 65,
                    "motivation": 60,
                    "youth_development": 55,
                    "judging_ability": 60,
                    "judging_potential": 60,
                    "adaptability": 60,
                    "discipline": 60,
                    "fitness_coaching": 50,
                    "set_piece_coaching": 50,
                    "negotiation": 55,
                    "media_handling": 50,
                },
                "press_style": {
                    "tone": PressTone.CALM,
                    "candour": 0.5,
                    "deflection": 0.3,
                    "blame_tendency": 0.2,
                    "bold_claims": 0.2,
                    "mind_games": 0.2,
                    "humor": 0.4,
                },
            }
        )
    )
    assert Manager.model_validate_json(manager.model_dump_json()) == manager
    assert manager.preferred_formation == FormationId("433")


def test_staff_and_referee__round_trip() -> None:
    staff = StaffMember.model_validate(
        _with_person(
            {
                "id": "stf_test0001",
                "club_id": "clb_home01",
                "role": StaffRole.PHYSIO,
                "quality": 60,
                "attrs": {
                    "coaching_technical": 50,
                    "coaching_mental": 50,
                    "coaching_physical": 50,
                    "tactical_input": 40,
                    "injury_treatment": 70,
                    "injury_prevention": 65,
                    "scouting_judgement": 40,
                    "scouting_network": 40,
                },
            }
        )
    )
    referee = Referee.model_validate(
        _with_person(
            {
                "id": "ref_test0001",
                "strictness": 0.5,
                "consistency": 0.7,
                "home_bias": 0.1,
                "card_tendency": 0.4,
                "advantage_tendency": 0.5,
                "added_time_generosity": 0.5,
                "penalty_propensity": 0.4,
                "video_reliance": 0.3,
                "fitness": 0.8,
            }
        )
    )
    assert isinstance(staff.attrs, StaffAttrs)
    assert StaffMember.model_validate_json(staff.model_dump_json()) == staff
    assert Referee.model_validate_json(referee.model_dump_json()) == referee
    assert staff.club_id == ClubId("clb_home01")
