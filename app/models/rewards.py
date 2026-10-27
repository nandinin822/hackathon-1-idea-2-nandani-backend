from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PlanningGoal(str, Enum):
    CHEAPEST_FLIGHT = "cheapest_flight"
    BUSINESS_CLASS = "business_class"
    EARN_FASTER = "earn_faster"


class RewardsPlanRequest(BaseModel):
    destination: str = Field(
        ...,
        description="Target destination city or IATA code",
        examples=["MAD", "Tokyo", "London"]
    )
    planning_horizon_months: int = Field(
        default=6,
        description="Planning period in months (1, 3, 6, 12)",
        examples=[6]
    )
    travel_goal: PlanningGoal = Field(
        default=PlanningGoal.CHEAPEST_FLIGHT,
        description="Travel hacking objective"
    )
    card_id: Optional[str] = Field(
        default=None,
        description="Card ID from catalogue, or None for general recommendation",
        examples=["us_chase_csp", "us_amex_gold"]
    )
    current_points: int = Field(
        default=0,
        ge=0,
        description="Current points balance already in user's account"
    )
    monthly_rent: float = Field(
        default=0.0,
        ge=0.0,
        description="Monthly rent or housing payments"
    )
    monthly_utilities: float = Field(
        default=0.0,
        ge=0.0,
        description="Monthly utilities, phone, internet"
    )
    monthly_groceries_dining: float = Field(
        default=0.0,
        ge=0.0,
        description="Monthly dining and grocery store spending"
    )
    monthly_travel: float = Field(
        default=0.0,
        ge=0.0,
        description="Monthly travel, hotels, transit"
    )
    monthly_other: float = Field(
        default=0.0,
        ge=0.0,
        description="Other general retail / shopping purchases"
    )
    currency: str = Field(
        default="USD",
        description="Expense currency"
    )
    annual_fee_preference: Optional[str] = Field(
        default="any",
        description="Annual fee preference: 'no_fee', 'under_100', 'any'"
    )

    @field_validator("planning_horizon_months")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        if v not in (1, 3, 6, 12):
            raise ValueError("Planning horizon must be 1, 3, 6, or 12 months.")
        return v


class MonthlyBreakdown(BaseModel):
    total_monthly_spend: float
    eligible_monthly_spend: float
    ineligible_monthly_spend: float
    ineligible_reasons: List[str] = []


class RewardsPlanResponse(BaseModel):
    destination: str
    planning_horizon_months: int
    travel_goal: PlanningGoal
    total_spend_horizon: float
    total_eligible_spend: float
    current_points: int
    estimated_points_earned: int
    projected_total_points: int
    monthly_breakdown: MonthlyBreakdown
    recommended_card: Optional[str] = None
    recommended_card_id: Optional[str] = None
    verified_card_annual_fee: Optional[float] = None
    recommendation_reason: str
    assumptions: List[str] = []
    warnings: List[str] = []
    is_calculable: bool = True
