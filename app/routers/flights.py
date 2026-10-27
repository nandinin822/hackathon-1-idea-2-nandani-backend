import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.models.flights import FlightCashSearchRequest, FlightSearchResponse
from app.services.duffel import (
    DuffelAPIError,
    DuffelConfigurationError,
    DuffelConnectionError,
    DuffelResponseError,
    DuffelService,
    DuffelTimeoutError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/flights", tags=["Flights"])


def get_duffel_service(settings: Settings = Depends(get_settings)) -> DuffelService:
    """Dependency provider for DuffelService instance configured with active settings."""
    return DuffelService(api_key=settings.DUFFEL_API_KEY)


@router.post(
    "/cash",
    response_model=FlightSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search cash flights via Duffel",
    description="Queries Duffel Flights API in test or live mode and returns structured flight offers.",
    responses={
        200: {"description": "Flight offers retrieved successfully."},
        400: {"description": "Invalid flight search parameters or provider rejection."},
        422: {"description": "Validation error for request fields (IATA codes, dates, etc.)."},
        502: {"description": "Bad gateway or upstream flight provider failure."},
        503: {"description": "Duffel API key is not configured."},
        504: {"description": "Flight provider timed out."},
    },
)
async def search_cash_flights(
    request: FlightCashSearchRequest,
    service: DuffelService = Depends(get_duffel_service),
) -> FlightSearchResponse:
    """
    Search cash flights with origin/destination IATA codes, dates, passengers, and cabin class.
    """
    try:
        return await service.search_cash_flights(request)
    except DuffelConfigurationError as exc:
        logger.error("Duffel service is not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except DuffelTimeoutError as exc:
        logger.warning("Duffel service request timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        )
    except DuffelConnectionError as exc:
        logger.error("Duffel connection error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    except DuffelAPIError as exc:
        logger.warning("Duffel API error (upstream %d): %s", exc.status_code, exc)
        # Map client-side errors (400, 422) to HTTP 400, and server errors to 502
        status_code = status.HTTP_400_BAD_REQUEST if exc.status_code in (400, 422) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        )
    except DuffelResponseError as exc:
        logger.error("Duffel response structure error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unhandled error during cash flight search: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred during flight search.",
        )
