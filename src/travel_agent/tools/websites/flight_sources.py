"""Per-website flight search tool adapters."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import httpx

from travel_agent.config import Settings, get_settings
from travel_agent.models import ToolError, ToolResult
from travel_agent.models.schemas import FlightOffer
from travel_agent.observability.logging import get_logger
from travel_agent.tools.websites._mock_helpers import build_mock_flight

logger = get_logger(__name__)

_SEARCH_TIMEOUT = 8.0


def _wrap(fn, source: str):
    try:
        from travel_agent.tools.websites._mock_helpers import enrich_flight_offer

        offers = [enrich_flight_offer(o) for o in fn()]
        return ToolResult(ok=True, data=offers)
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s flight search failed", source)
        return ToolResult(
            ok=False,
            error=ToolError(
                code=f"{source}_flight_search_exception",
                message=str(exc),
                retryable=True,
                details={"source": source},
            ),
        )


def search_google_flights(
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    return_date: Optional[date] = None,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "google_flights"

    def _mock() -> List[FlightOffer]:
        return [
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="DL",
                stops=0,
                base_price=312,
                price_jitter=-12,
                dep_hour=7,
                flight_no_prefix="DL",
            ),
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="UA",
                stops=1,
                base_price=268,
                price_jitter=0,
                dep_hour=11,
                flight_no_prefix="UA",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)

    try:
        with httpx.Client(timeout=_SEARCH_TIMEOUT) as client:
            client.get(
                "https://www.google.com/travel/flights",
                params={"q": f"Flights from {origin} to {destination} on {departure_date}"},
            )
    except httpx.HTTPError:
        pass
    return _wrap(_mock, source)


def search_kayak(
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    return_date: Optional[date] = None,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "kayak"

    def _mock() -> List[FlightOffer]:
        return [
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="B6",
                stops=0,
                base_price=289,
                price_jitter=8,
                dep_hour=9,
                flight_no_prefix="B6",
            ),
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="AA",
                stops=2,
                base_price=241,
                price_jitter=-5,
                dep_hour=14,
                flight_no_prefix="AA",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


def search_expedia_flights(
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    return_date: Optional[date] = None,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "expedia"

    def _mock() -> List[FlightOffer]:
        return [
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="AS",
                stops=1,
                base_price=255,
                price_jitter=15,
                dep_hour=6,
                flight_no_prefix="AS",
            ),
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="WN",
                stops=0,
                base_price=334,
                price_jitter=-8,
                dep_hour=16,
                flight_no_prefix="WN",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


def search_booking_com_flights(
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    return_date: Optional[date] = None,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "booking.com"

    def _mock() -> List[FlightOffer]:
        return [
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="LH",
                stops=1,
                base_price=278,
                price_jitter=4,
                dep_hour=10,
                flight_no_prefix="LH",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


def search_airline_direct(
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    return_date: Optional[date] = None,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "airline_direct"

    def _mock() -> List[FlightOffer]:
        return [
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="BA",
                stops=0,
                base_price=358,
                price_jitter=-20,
                dep_hour=8,
                flight_no_prefix="BA",
            ),
            build_mock_flight(
                source=source,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                carrier="AF",
                stops=1,
                base_price=299,
                price_jitter=10,
                dep_hour=13,
                flight_no_prefix="AF",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


FLIGHT_SITE_TOOLS = {
    "search_google_flights": search_google_flights,
    "search_kayak": search_kayak,
    "search_expedia": search_expedia_flights,
    "search_booking_com": search_booking_com_flights,
    "search_airline_direct": search_airline_direct,
}
