"""
Duffel Flights API Service Integration.

Handles offer-request creation and cash flight searching via Duffel API v2.
Security & architecture guarantees:
- Kept strictly behind the backend service interface.
- Never logs or exposes API tokens in logs, exceptions, or API responses.
- Sensible timeouts applied to all external HTTP requests.
- Does not fabricate flight prices, schedules, or availability.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.models.flights import (
    AirportLocation,
    FlightCashSearchRequest,
    FlightOfferResponse,
    FlightSearchResponse,
    FlightSegmentResponse,
    FlightSliceResponse,
)

logger = logging.getLogger(__name__)


# --- Domain Exceptions ---

class DuffelError(Exception):
    """Base exception for all Duffel service errors."""
    pass


class DuffelConfigurationError(DuffelError):
    """Raised when Duffel API credentials are missing or invalidly configured."""
    pass


class DuffelTimeoutError(DuffelError):
    """Raised when an external request to Duffel times out."""
    pass


class DuffelConnectionError(DuffelError):
    """Raised when network connectivity to Duffel fails."""
    pass


class DuffelAPIError(DuffelError):
    """Raised when Duffel returns an error status code."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class DuffelResponseError(DuffelError):
    """Raised when Duffel returns unexpected or unparseable response data."""
    pass


# --- Service Client ---

class DuffelService:
    """
    Client for Duffel Air API v2.
    """

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = 25.0):
        self._api_key = (api_key or "").strip()
        self.base_url = "https://api.duffel.com"
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        """Indicates whether a Duffel API token is present."""
        return bool(self._api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Builds sanitized Duffel v2 headers."""
        if not self.is_configured:
            raise DuffelConfigurationError(
                "Duffel API key is not configured. Cash flight search is currently unavailable."
            )
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_offer_request_payload(self, request: FlightCashSearchRequest) -> Dict[str, Any]:
        """Converts validated search parameters into Duffel offer-request payload."""
        slices = [
            {
                "origin": request.origin,
                "destination": request.destination,
                "departure_date": request.departure_date.isoformat(),
            }
        ]
        if request.return_date:
            slices.append({
                "origin": request.destination,
                "destination": request.origin,
                "departure_date": request.return_date.isoformat(),
            })

        passengers = [{"type": "adult"} for _ in range(request.passengers)]

        return {
            "data": {
                "slices": slices,
                "passengers": passengers,
                "cabin_class": request.cabin_class.value,
            }
        }

    def _parse_airport_location(self, data: Optional[Dict[str, Any]]) -> AirportLocation:
        """Parses airport data safely."""
        if not data or not isinstance(data, dict):
            return AirportLocation(iata_code="UNK")
        return AirportLocation(
            iata_code=data.get("iata_code") or "UNK",
            name=data.get("name"),
            city_name=data.get("city_name") or (data.get("city") or {}).get("name"),
        )

    def _parse_offer_response(self, raw_data: Dict[str, Any]) -> FlightSearchResponse:
        """Transforms Duffel raw response payload into normalized FlightSearchResponse."""
        try:
            data = raw_data.get("data")
            if not isinstance(data, dict):
                raise DuffelResponseError("Invalid response structure received from flight provider.")

            search_id = data.get("id")
            raw_offers = data.get("offers", [])
            if not isinstance(raw_offers, list):
                raw_offers = []

            parsed_offers: List[FlightOfferResponse] = []

            for offer in raw_offers:
                offer_id = offer.get("id")
                if not offer_id:
                    continue

                total_amount = str(offer.get("total_amount", "0.00"))
                currency = str(offer.get("total_currency", "USD"))
                try:
                    total_price = float(total_amount)
                except (ValueError, TypeError):
                    total_price = 0.0

                owner = offer.get("owner") or {}
                airline_name = owner.get("name")
                airline_code = owner.get("iata_code")

                parsed_slices: List[FlightSliceResponse] = []
                for slice_item in offer.get("slices", []):
                    slice_id = slice_item.get("id")
                    origin_loc = self._parse_airport_location(slice_item.get("origin"))
                    dest_loc = self._parse_airport_location(slice_item.get("destination"))
                    duration = slice_item.get("duration")

                    parsed_segments: List[FlightSegmentResponse] = []
                    for seg in slice_item.get("segments", []):
                        seg_origin = self._parse_airport_location(seg.get("origin"))
                        seg_dest = self._parse_airport_location(seg.get("destination"))
                        carrier = seg.get("operating_carrier") or seg.get("marketing_carrier") or {}
                        flight_num = (
                            seg.get("operating_carrier_flight_number")
                            or seg.get("marketing_carrier_flight_number")
                        )

                        parsed_segments.append(
                            FlightSegmentResponse(
                                id=seg.get("id"),
                                origin=seg_origin,
                                destination=seg_dest,
                                departing_at=seg.get("departing_at") or "",
                                arriving_at=seg.get("arriving_at") or "",
                                carrier_name=carrier.get("name"),
                                carrier_code=carrier.get("iata_code"),
                                flight_number=flight_num,
                                duration=seg.get("duration"),
                            )
                        )

                    parsed_slices.append(
                        FlightSliceResponse(
                            id=slice_id,
                            origin=origin_loc,
                            destination=dest_loc,
                            duration=duration,
                            segments=parsed_segments,
                        )
                    )

                parsed_offers.append(
                    FlightOfferResponse(
                        id=offer_id,
                        total_price=total_price,
                        total_amount=total_amount,
                        currency=currency,
                        airline_name=airline_name,
                        airline_code=airline_code,
                        cabin_class=data.get("cabin_class"),
                        is_demo=not bool(data.get("live_mode", False)),
                        booking_url=None,
                        slices=parsed_slices,
                        provider="duffel",
                    )
                )

            live_mode = bool(data.get("live_mode", False))
            return FlightSearchResponse(
                search_id=search_id,
                total_offers=len(parsed_offers),
                offers=parsed_offers,
                provider="duffel",
                live_mode=live_mode,
                is_demo=not live_mode,
                demo_notice=(
                    "Duffel Sandbox Mode: Realistic test flight offers provided by the Duffel test airline. Fares and schedules are simulated."
                    if not live_mode
                    else None
                ),
            )
        except DuffelResponseError:
            raise
        except Exception as exc:
            logger.error("Failed to parse flight offers from provider: %s", type(exc).__name__)
            raise DuffelResponseError("Error parsing flight offers from provider.") from exc

    async def search_cash_flights(self, request: FlightCashSearchRequest) -> FlightSearchResponse:
        """
        Executes an offer request with Duffel and returns parsed flight offers.
        """
        if not self.is_configured:
            raise DuffelConfigurationError(
                "Duffel API key is not configured. Cash flight search is currently unavailable."
            )

        headers = self._get_headers()
        payload = self._build_offer_request_payload(request)
        url = f"{self.base_url}/air/offer_requests?return_offers=true"

        logger.info(
            "Searching cash flights via Duffel | origin=%s, destination=%s, departure=%s, return=%s, passengers=%d, cabin=%s",
            request.origin,
            request.destination,
            request.departure_date,
            request.return_date,
            request.passengers,
            request.cabin_class.value,
        )

        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("Duffel flight search timed out after %s seconds", self.timeout_seconds)
            raise DuffelTimeoutError(
                "Flight search request timed out while contacting provider. Please try again."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Network error while connecting to Duffel: %s", type(exc).__name__)
            raise DuffelConnectionError(
                "Unable to connect to flight search provider. Please check network connectivity."
            ) from exc

        # Handle non-2xx responses
        if response.status_code not in (200, 201):
            error_message = self._extract_duffel_error_message(response)
            logger.warning("Duffel API returned status %d: %s", response.status_code, error_message)
            raise DuffelAPIError(message=error_message, status_code=response.status_code)

        try:
            raw_data = response.json()
        except Exception as exc:
            logger.error("Duffel returned invalid JSON: %s", type(exc).__name__)
            raise DuffelResponseError("Flight search provider returned unparseable data.") from exc

        return self._parse_offer_response(raw_data)

    def _extract_duffel_error_message(self, response: httpx.Response) -> str:
        """Safely extracts error message from Duffel error response without leaking tokens or internal details."""
        try:
            body = response.json()
            errors = body.get("errors")
            if isinstance(errors, list) and errors:
                first_err = errors[0]
                if isinstance(first_err, dict):
                    msg = first_err.get("message") or first_err.get("title")
                    if msg:
                        return f"Provider error: {msg}"
            return f"Flight provider returned error code {response.status_code}."
        except Exception:
            return f"Flight provider returned error code {response.status_code}."

    def generate_demo_offers(self, request: FlightCashSearchRequest) -> FlightSearchResponse:
        """
        Generates structured, explicitly labeled demo offers when the live Duffel API
        is not configured. Used strictly in demo/development mode and never replaces
        failed live calls.
        """
        dep_date_str = request.departure_date.isoformat()
        ret_date_str = request.return_date.isoformat() if request.return_date else None
        cabin_str = request.cabin_class.value
        base_price = 450.0 if cabin_str == "economy" else (850.0 if cabin_str == "premium_economy" else 1850.0)
        
        sample_carriers = [
            ("Iberia", "IB", "IB3160", 1.0, "PT7H45M"),
            ("British Airways", "BA", "BA0178", 1.15, "PT8H10M"),
            ("Delta Air Lines", "DL", "DL0126", 1.25, "PT8H30M"),
        ]

        offers: List[FlightOfferResponse] = []
        for idx, (carrier_name, carrier_code, flight_num, multiplier, duration) in enumerate(sample_carriers, 1):
            price = round(base_price * multiplier * request.passengers, 2)
            amount_str = f"{price:.2f}"
            
            outbound_slice = FlightSliceResponse(
                id=f"sli_demo_out_{idx}",
                origin=AirportLocation(iata_code=request.origin, name=f"{request.origin} International Airport"),
                destination=AirportLocation(iata_code=request.destination, name=f"{request.destination} Airport"),
                duration=duration,
                departure_date=dep_date_str,
                segments=[
                    FlightSegmentResponse(
                        id=f"seg_demo_out_{idx}",
                        origin=AirportLocation(iata_code=request.origin, name=f"{request.origin} International Airport"),
                        destination=AirportLocation(iata_code=request.destination, name=f"{request.destination} Airport"),
                        departing_at=f"{dep_date_str}T09:30:00",
                        arriving_at=f"{dep_date_str}T17:15:00",
                        carrier_name=carrier_name,
                        carrier_code=carrier_code,
                        flight_number=flight_num,
                        duration=duration,
                    )
                ]
            )
            slices = [outbound_slice]

            if ret_date_str:
                return_slice = FlightSliceResponse(
                    id=f"sli_demo_ret_{idx}",
                    origin=AirportLocation(iata_code=request.destination, name=f"{request.destination} Airport"),
                    destination=AirportLocation(iata_code=request.origin, name=f"{request.origin} International Airport"),
                    duration=duration,
                    departure_date=ret_date_str,
                    segments=[
                        FlightSegmentResponse(
                            id=f"seg_demo_ret_{idx}",
                            origin=AirportLocation(iata_code=request.destination, name=f"{request.destination} Airport"),
                            destination=AirportLocation(iata_code=request.origin, name=f"{request.origin} International Airport"),
                            departing_at=f"{ret_date_str}T11:00:00",
                            arriving_at=f"{ret_date_str}T18:45:00",
                            carrier_name=carrier_name,
                            carrier_code=carrier_code,
                            flight_number=f"{carrier_code}9{idx}1",
                            duration=duration,
                        )
                    ]
                )
                slices.append(return_slice)

            offers.append(
                FlightOfferResponse(
                    id=f"off_demo_{request.origin}_{request.destination}_{idx}",
                    total_price=price,
                    total_amount=amount_str,
                    currency="USD",
                    airline_name=carrier_name,
                    airline_code=carrier_code,
                    cabin_class=cabin_str,
                    is_demo=True,
                    booking_url=f"https://www.{carrier_name.lower().replace(' ', '')}.com",
                    slices=slices,
                    provider="duffel_demo_fixture",
                )
            )

        return FlightSearchResponse(
            search_id=f"sea_demo_{request.origin}_{request.destination}",
            total_offers=len(offers),
            offers=offers,
            provider="duffel_demo_fixture",
            live_mode=False,
            is_demo=True,
            demo_notice="DEMO DATA: Duffel API key is unconfigured on backend. Showing illustrative test fixture data for development and review.",
        )
