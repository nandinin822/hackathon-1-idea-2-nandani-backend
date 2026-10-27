import logging
from fastapi import APIRouter, status

from app.models.rewards import RewardsPlanRequest, RewardsPlanResponse
from app.services.rewards_planner import RewardsPlannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rewards", tags=["Rewards"])

service = RewardsPlannerService()


@router.post(
    "/plan",
    response_model=RewardsPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate future rewards plan",
    description="Deterministic calculation of future points accumulation over 1, 3, 6, or 12 months based on verified card earning rules.",
)
async def calculate_rewards_plan(request: RewardsPlanRequest) -> RewardsPlanResponse:
    """
    Calculates monthly eligible spend, projected points, and recommendations
    based strictly on verified credit card terms and user expense profiles.
    """
    logger.info(
        "Calculating rewards plan | destination=%s, horizon=%d months, goal=%s, card=%s",
        request.destination,
        request.planning_horizon_months,
        request.travel_goal.value,
        request.card_id,
    )
    return service.calculate_plan(request)
