import logging
from typing import Dict, Any, Tuple
from app.models.rewards import (
    PlanningGoal,
    RewardsPlanRequest,
    RewardsPlanResponse,
    MonthlyBreakdown,
)

logger = logging.getLogger(__name__)

# Verified Card Profiles and Earning Multipliers (strictly from public terms)
VERIFIED_CARD_DATA: Dict[str, Dict[str, Any]] = {
    "us_chase_csp": {
        "name": "Chase Sapphire Preferred®",
        "market": "US",
        "annual_fee": 95.0,
        "multipliers": {
            "groceries_dining": 3.0,
            "travel": 2.0,
            "utilities": 1.0,
            "other": 1.0,
            "rent": 0.0,
        },
        "program": "Chase Ultimate Rewards®",
        "best_for": "General flexible travel transfer with low annual fee ($95).",
    },
    "us_amex_gold": {
        "name": "American Express® Gold Card",
        "market": "US",
        "annual_fee": 325.0,
        "multipliers": {
            "groceries_dining": 4.0,
            "travel": 3.0,
            "utilities": 1.0,
            "other": 1.0,
            "rent": 0.0,
        },
        "program": "Membership Rewards®",
        "best_for": "Supermarkets and dining (4x multiplier).",
    },
    "us_capone_venture_x": {
        "name": "Capital One Venture X Rewards",
        "market": "US",
        "annual_fee": 395.0,
        "multipliers": {
            "groceries_dining": 2.0,
            "travel": 2.0,
            "utilities": 2.0,
            "other": 2.0,
            "rent": 0.0,
        },
        "program": "Capital One Miles",
        "best_for": "Flat 2x earning on all general and everyday purchases.",
    },
    "us_bilt_rewards": {
        "name": "Bilt World Elite Mastercard®",
        "market": "US",
        "annual_fee": 0.0,
        "multipliers": {
            "groceries_dining": 3.0,
            "travel": 2.0,
            "utilities": 1.0,
            "other": 1.0,
            "rent": 1.0,
        },
        "program": "Bilt Rewards",
        "best_for": "Fee-free rent points earning (1x points on rent).",
    },
    "es_amex_platinum": {
        "name": "American Express® Platinum España",
        "market": "ES",
        "annual_fee": 780.0,
        "multipliers": {
            "groceries_dining": 1.0,
            "travel": 1.0,
            "utilities": 1.0,
            "other": 1.0,
            "rent": 0.0,
        },
        "program": "Membership Rewards® ES",
        "best_for": "Luxury lounge access and premium international travel protections.",
    },
    "es_iberia_icon": {
        "name": "Iberia Cards ICON",
        "market": "ES",
        "annual_fee": 100.0,
        "multipliers": {
            "groceries_dining": 0.5,
            "travel": 1.0,
            "utilities": 0.5,
            "other": 0.5,
            "rent": 0.0,
        },
        "program": "Iberia Plus Avios",
        "best_for": "Direct Iberia Plus Avios deposit and 10% flight discount.",
    },
}


class RewardsPlannerService:
    """
    Deterministic calculation service for future rewards estimation.
    Applies verified earning rules and strictly excludes ineligible categories.
    """

    def calculate_plan(self, req: RewardsPlanRequest) -> RewardsPlanResponse:
        card = VERIFIED_CARD_DATA.get(req.card_id) if req.card_id else None

        # Determine effective card profile or default
        if card:
            multipliers = card["multipliers"]
            card_name = card["name"]
            card_id = req.card_id
            annual_fee = card["annual_fee"]
        else:
            # Baseline estimation if no card selected
            card_name, card_id, multipliers, annual_fee = self._select_recommended_card(req)

        # 1. Monthly Breakdown Calculation
        total_monthly_spend = round(
            req.monthly_rent
            + req.monthly_utilities
            + req.monthly_groceries_dining
            + req.monthly_travel
            + req.monthly_other,
            2,
        )

        ineligible_reasons = []
        eligible_monthly_spend = 0.0

        # Rent eligibility check
        if multipliers.get("rent", 0.0) > 0.0:
            eligible_monthly_spend += req.monthly_rent
        elif req.monthly_rent > 0:
            ineligible_reasons.append(
                f"Monthly rent (${req.monthly_rent:,.2f}) does not earn points on {card_name}. Most credit cards charge a 2.5–3.0% processing fee for rent payments unless using Bilt."
            )

        # Other categories
        eligible_monthly_spend += req.monthly_utilities
        eligible_monthly_spend += req.monthly_groceries_dining
        eligible_monthly_spend += req.monthly_travel
        eligible_monthly_spend += req.monthly_other

        eligible_monthly_spend = round(eligible_monthly_spend, 2)
        ineligible_monthly_spend = round(total_monthly_spend - eligible_monthly_spend, 2)

        monthly_breakdown = MonthlyBreakdown(
            total_monthly_spend=total_monthly_spend,
            eligible_monthly_spend=eligible_monthly_spend,
            ineligible_monthly_spend=ineligible_monthly_spend,
            ineligible_reasons=ineligible_reasons,
        )

        # 2. Monthly Points Earned
        monthly_points = (
            (req.monthly_rent * multipliers.get("rent", 0.0))
            + (req.monthly_groceries_dining * multipliers.get("groceries_dining", 1.0))
            + (req.monthly_travel * multipliers.get("travel", 1.0))
            + (req.monthly_utilities * multipliers.get("utilities", 1.0))
            + (req.monthly_other * multipliers.get("other", 1.0))
        )

        horizon = req.planning_horizon_months
        total_spend_horizon = round(total_monthly_spend * horizon, 2)
        total_eligible_spend = round(eligible_monthly_spend * horizon, 2)
        estimated_points_earned = int(round(monthly_points * horizon))
        projected_total = req.current_points + estimated_points_earned

        # 3. Transparent Assumptions & Warnings
        assumptions = [
            f"Calculated over a {horizon}-month horizon assuming steady monthly spend.",
            f"Earning rates applied: Groceries/Dining {multipliers.get('groceries_dining', 1.0)}x, Travel {multipliers.get('travel', 1.0)}x, Rent {multipliers.get('rent', 0.0)}x, Other {multipliers.get('other', 1.0)}x.",
            "Estimates exclude sign-up bonuses, introductory promotional APRs, and quarterly rotating categories.",
            "Card approval is subject to credit check by the issuer.",
        ]

        warnings = []
        if total_monthly_spend == 0:
            warnings.append("All spending categories were entered as zero. Enter your typical monthly expenses to estimate points.")
        if req.travel_goal == PlanningGoal.BUSINESS_CLASS and projected_total < 40000:
            warnings.append(f"Targeting Business Class typically requires 45,000–80,000 points per passenger. Your projected total ({projected_total:,} pts) may require a longer horizon or higher spend.")
        if req.monthly_rent > 1500 and multipliers.get("rent", 0.0) == 0:
            warnings.append("Consider a card that supports fee-free rent payments (such as Bilt) to earn points on your largest monthly expense.")

        # Recommendation Reason
        reason = self._build_recommendation_reason(req, card_name, projected_total)

        return RewardsPlanResponse(
            destination=req.destination,
            planning_horizon_months=horizon,
            travel_goal=req.travel_goal,
            total_spend_horizon=total_spend_horizon,
            total_eligible_spend=total_eligible_spend,
            current_points=req.current_points,
            estimated_points_earned=estimated_points_earned,
            projected_total_points=projected_total,
            monthly_breakdown=monthly_breakdown,
            recommended_card=card_name,
            recommended_card_id=card_id,
            verified_card_annual_fee=annual_fee,
            recommendation_reason=reason,
            assumptions=assumptions,
            warnings=warnings,
            is_calculable=True,
        )

    def _select_recommended_card(self, req: RewardsPlanRequest) -> Tuple[str, str, Dict[str, float], float]:
        """Selects the most suitable card profile based on user spending composition and goal."""
        if req.annual_fee_preference == "no_fee" or req.monthly_rent > (req.monthly_groceries_dining * 1.5):
            card = VERIFIED_CARD_DATA["us_bilt_rewards"]
            return card["name"], "us_bilt_rewards", card["multipliers"], card["annual_fee"]

        if req.monthly_groceries_dining > req.monthly_other and req.annual_fee_preference != "no_fee":
            card = VERIFIED_CARD_DATA["us_amex_gold"]
            return card["name"], "us_amex_gold", card["multipliers"], card["annual_fee"]

        # Default versatile travel card
        card = VERIFIED_CARD_DATA["us_chase_csp"]
        return card["name"], "us_chase_csp", card["multipliers"], card["annual_fee"]

    def _build_recommendation_reason(self, req: RewardsPlanRequest, card_name: str, projected_points: int) -> str:
        goal_text = {
            PlanningGoal.CHEAPEST_FLIGHT: f"save money on flights to {req.destination}",
            PlanningGoal.BUSINESS_CLASS: f"book premium cabin award space to {req.destination}",
            PlanningGoal.EARN_FASTER: "maximize points accumulation velocity across everyday spend",
        }.get(req.travel_goal, "reach your travel goals")

        return (
            f"Based on your goal to {goal_text}, {card_name} provides the most effective multiplier alignment. "
            f"Over {req.planning_horizon_months} months, you are projected to reach approximately {projected_points:,} total points."
        )
