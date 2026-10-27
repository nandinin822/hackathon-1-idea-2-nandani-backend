from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    """
    Health check endpoint for Render monitoring and uptime checks.
    Returns HTTP 200 with basic status indicator.
    Does not expose sensitive environment data or API keys.
    """
    return HealthResponse(status="ok")
