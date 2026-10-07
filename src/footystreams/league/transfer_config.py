"""Transfer configuration models (``data/static/transfer.yaml``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScoutingConfig(_Config):
    """How noisily a club judges a player."""

    noise_at_zero_judging: float = Field(ge=0.0)
    potential_factor: float = Field(ge=1.0)
    default_judging: int = Field(ge=0, le=100)
    confidence_floor: float = Field(ge=0.0, le=1.0)


class ValuationConfig(_Config):
    """Bidding and the seller's reservation price."""

    rounds: int = Field(ge=1, le=3)
    desire_weight: float
    urgency_weight: float
    bid_noise: float = Field(ge=0.0)
    reservation_floor: float = Field(gt=0.0, le=1.0)
    financial_discount: float = Field(ge=0.0, lt=1.0)
    role_stubbornness: dict[str, float]
    round_concession: float = Field(ge=0.0, le=1.0)
    ceiling_margin: float = Field(ge=0.0)
    desire_scale: int = Field(ge=1)
    youth_age: int
    youth_weight: float = Field(ge=0.0)


class NeedsConfig(_Config):
    """What makes a club want a player."""

    position_minimum: dict[str, int]
    upgrade_margin: int = Field(ge=0)
    max_age: int
    max_signing_share: float = Field(gt=0.0, le=1.0)
    wage_headroom: float = Field(ge=1.0)


class TermsConfig(_Config):
    """Player contract terms and willingness."""

    wage_rounds: tuple[float, ...]
    length_years: tuple[int, int]
    ambition_weight: float
    wage_weight: float
    free_agent_bonus: float
    mood_weight: float
    threshold: float


class MedicalConfig(_Config):
    """Medical failure chances."""

    base_failure: float = Field(ge=0.0, le=1.0)
    proneness_weight: float = Field(ge=0.0)
    injured_failure: float = Field(ge=0.0, le=1.0)


class WindowConfig(_Config):
    """Window activity limits."""

    buyers_per_day: int = Field(ge=1)
    deals_per_club: int = Field(ge=1)
    panic_days: int = Field(ge=0)
    listing_markup: float = Field(gt=0.0)


class SalesConfig(_Config):
    """When clubs put players up for sale."""

    surplus_over: int
    financial_balance_share: float = Field(ge=0.0)
    unhappy_kinds: tuple[str, ...]


class OutsideConfig(_Config):
    """The synthetic market of clubs outside the league."""

    supply_size: int = Field(ge=0)
    supply_ability: tuple[float, float]
    supply_age: tuple[int, int]
    bid_rate: float = Field(ge=0.0, le=1.0)
    bid_premium: float = Field(gt=0.0)
    bid_min_ability: float = Field(ge=0.0)


class RenewalConfig(_Config):
    """Contract renewal talks."""

    role_tolerance: dict[str, int]
    max_age: int
    loyalty_weight: float
    dispute_magnitude: float = Field(ge=0.0, le=1.0)


class TransferConfig(_Config):
    """Everything in ``transfer.yaml``."""

    scouting: ScoutingConfig
    valuation: ValuationConfig
    needs: NeedsConfig
    terms: TermsConfig
    medical: MedicalConfig
    window: WindowConfig
    sales: SalesConfig
    outside: OutsideConfig
    renewal: RenewalConfig
