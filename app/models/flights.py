from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class FlightCashSearchRequest(BaseModel):
    """
    Request model for cash flight search.
    Validates origin/destination IATA codes, dates, passenger count, and cabin class.
    """
    origin: str = Field(
        ...,
        description="3-letter IATA airport code for origin (e.g., JFK, MAD, BOG)",
        examples=["JFK"]
    )
    destination: str = Field(
        ...,
        description="3-letter IATA airport code for destination (e.g., LHR, CDG, MIA)",
        examples=["LHR"]
    )
    departure_date: date = Field(
        ...,
        description="Departure date (YYYY-MM-DD)",
        examples=["2026-11-15"]
    )
    return_date: Optional[date] = Field(
        default=None,
        description="Optional return date for round trips (YYYY-MM-DD)",
        examples=["2026-11-22"]
    )
    passengers: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Number of adult passengers (1-9)"
    )
    cabin_class: CabinClass = Field(
        default=CabinClass.ECONOMY,
        description="Cabin class: economy, premium_economy, business, or first"
    )

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata_code(cls, v: str) -> str:
        code = v.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("Airport code must be a valid 3-letter alphabetic IATA code.")
        return code

    @model_validator(mode="after")
    def validate_trip_dates_and_airports(self) -> "FlightCashSearchRequest":
        if self.origin == self.destination:
            raise ValueError("Origin and destination airport codes cannot be the same.")

        today = date.today()
        if self.departure_date < today:
            raise ValueError("Departure date cannot be in the past.")

        if self.return_date is not None:
            if self.return_date < self.departure_date:
                raise ValueError("Return date must be on or after departure date.")

        return self


# --- Response Models ---

class AirportLocation(BaseModel):
    iata_code: str
    name: Optional[str] = None
    city_name: Optional[str] = None


class FlightSegmentResponse(BaseModel):
    id: Optional[str] = None
    origin: AirportLocation
    destination: AirportLocation
    departing_at: str
    arriving_at: str
    carrier_name: Optional[str] = None
    carrier_code: Optional[str] = None
    flight_number: Optional[str] = None
    duration: Optional[str] = None


class FlightSliceResponse(BaseModel):
    id: Optional[str] = None
    origin: AirportLocation
    destination: AirportLocation
    departure_date: Optional[str] = None
    duration: Optional[str] = None
    segments: List[FlightSegmentResponse] = []


class FlightOfferResponse(BaseModel):
    id: str
    total_price: float
    total_amount: str
    currency: str
    airline_name: Optional[str] = None
    airline_code: Optional[str] = None
    slices: List[FlightSliceResponse] = []
    provider: str = "duffel"


class FlightSearchResponse(BaseModel):
    search_id: Optional[str] = None
    total_offers: int
    offers: List[FlightOfferResponse]
    provider: str = "duffel"
