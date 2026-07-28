"""Pydantic domain schemas for trips, itineraries, auth, and bookings."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


class TripState(str, Enum):
    INTAKE = "INTAKE"
    CONSTRAINTS = "CONSTRAINTS"
    SEARCH = "SEARCH"
    COMPARE = "COMPARE"
    TRAVELERS = "TRAVELERS"
    RANK = "RANK"
    PROPOSE = "PROPOSE"
    AWAIT_APPROVAL = "AWAIT_APPROVAL"
    BOOK = "BOOK"
    CONFIRM = "CONFIRM"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"


class Traveler(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None


class TripConstraints(BaseModel):
    origin: Optional[str] = Field(None, description="IATA origin airport code")
    destination: Optional[str] = Field(None, description="IATA destination airport code")
    destination_city: Optional[str] = None
    departure_date: Optional[date] = None
    return_date: Optional[date] = None
    adults: int = Field(1, ge=1, le=9)
    budget_usd: Optional[float] = Field(None, gt=0)
    hotel_stars_min: Optional[int] = None
    preferences: List[str] = Field(default_factory=list)
    preferences_text: Optional[str] = None
    travelers: List[Traveler] = Field(default_factory=list)

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def upper_iata(cls, v: Optional[str]) -> Optional[str]:
        return v.upper().strip() if isinstance(v, str) and v else v


class FlightSegment(BaseModel):
    origin: str
    origin_name: Optional[str] = None
    destination: str
    destination_name: Optional[str] = None
    departure_at: str
    arrival_at: str
    duration: Optional[str] = None
    carrier: str
    carrier_name: Optional[str] = None
    flight_number: Optional[str] = None
    aircraft: Optional[str] = None
    cabin: Optional[str] = None
    layover_city: Optional[str] = None  # legacy; prefer offer.layovers


class LayoverInfo(BaseModel):
    airport: str
    airport_name: Optional[str] = None
    city: Optional[str] = None
    duration_minutes: int


class FlightOffer(BaseModel):
    offer_id: str
    source: str = Field(default="unknown", description="OTA or airline website")
    carrier: str
    carrier_name: Optional[str] = None
    origin: str
    origin_name: Optional[str] = None
    destination: str
    destination_name: Optional[str] = None
    departure_at: str
    arrival_at: str
    duration: str
    stops: int = 0
    segments: List[FlightSegment] = Field(default_factory=list)
    layovers: List[LayoverInfo] = Field(default_factory=list)
    cabin: Optional[str] = "ECONOMY"
    price_usd: float
    currency: str = "USD"
    deep_link: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class HotelOffer(BaseModel):
    offer_id: str
    source: str = Field(default="unknown", description="Hotel booking website")
    hotel_id: str
    name: str
    city: str
    check_in: date
    check_out: date
    price_usd: float
    currency: str = "USD"
    rating: Optional[float] = None
    address: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class RankedPair(BaseModel):
    flight_offer_id: str
    hotel_offer_id: str
    total_usd: float
    within_budget: bool
    score: float


class DailyWeatherForecast(BaseModel):
    date: date
    temp_high_c: float
    temp_low_c: float
    description: str
    precipitation_chance: Optional[int] = None


class WeatherSummary(BaseModel):
    location: str
    temp_c: float
    description: str
    humidity: Optional[int] = None
    daily: List[DailyWeatherForecast] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    place_name: str
    rating: float
    review_count: int
    snippets: List[str] = Field(default_factory=list)


class ProposedItinerary(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    flight: Optional[FlightOffer] = None
    hotel: Optional[HotelOffer] = None
    weather: Optional[WeatherSummary] = None
    reviews: Optional[ReviewSummary] = None
    total_usd: float = 0.0
    within_budget: bool = True
    summary: str = ""
    itinerary_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class BookingRecord(BaseModel):
    booking_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    provider_ref: str
    status: str
    amount_usd: float
    idempotency_key: str
    raw: Dict[str, Any] = Field(default_factory=dict)


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    trip_id: str
    proposal_id: str
    itinerary_hash: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: str = "user"
    acknowledge_over_budget: bool = False


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None


class TripCreateRequest(BaseModel):
    constraints: TripConstraints
    preferences_text: Optional[str] = None


class TripSelectRequest(BaseModel):
    flight_offer_id: str
    hotel_offer_id: str


class TravelersUpdateRequest(BaseModel):
    travelers: List[Traveler] = Field(..., min_length=1)


class TripApproveRequest(BaseModel):
    proposal_id: str
    itinerary_hash: str
    acknowledge_over_budget: bool = False


class TripRejectRequest(BaseModel):
    proposal_id: Optional[str] = None
    feedback: Optional[str] = None
    research: bool = True


class ToolCallEvent(BaseModel):
    tool: str
    status: str  # started | ok | error
    summary: str = ""
    args: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = None
    created_at: Optional[datetime] = None


class TripResponse(BaseModel):
    trip_id: UUID
    user_id: Optional[str] = None
    state: TripState
    constraints: TripConstraints
    flight_offers: List[FlightOffer] = Field(default_factory=list)
    hotel_offers: List[HotelOffer] = Field(default_factory=list)
    ranked_pairs: List[RankedPair] = Field(default_factory=list)
    selected_flight_id: Optional[str] = None
    selected_hotel_id: Optional[str] = None
    proposal: Optional[ProposedItinerary] = None
    weather: Optional[WeatherSummary] = None
    daily_weather: List[DailyWeatherForecast] = Field(default_factory=list)
    reviews: Optional[ReviewSummary] = None
    bookings: List[BookingRecord] = Field(default_factory=list)
    approval: Optional[ApprovalRecord] = None
    tool_calls: List[ToolCallEvent] = Field(default_factory=list)
    error: Optional[str] = None
    error_code: Optional[str] = None
    retryable: bool = False
    cost_usd: float = 0.0
    steps: int = 0
    proposal_expires_at: Optional[datetime] = None


class TripSummary(BaseModel):
    trip_id: UUID
    state: TripState
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[date] = None
    return_date: Optional[date] = None
    total_usd: Optional[float] = None
    updated_at: Optional[datetime] = None


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool
    data: Optional[Any] = None
    error: Optional[ToolError] = None
