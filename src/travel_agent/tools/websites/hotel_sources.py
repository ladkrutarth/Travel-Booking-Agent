"""Per-website hotel search tool adapters."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from travel_agent.config import Settings, get_settings
from travel_agent.models import ToolError, ToolResult
from travel_agent.models.schemas import HotelOffer
from travel_agent.observability.logging import get_logger
from travel_agent.tools.websites._mock_helpers import build_mock_hotel, city_label

logger = get_logger(__name__)


def _wrap(fn, source: str):
    try:
        offers = fn()
        return ToolResult(ok=True, data=offers)
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s hotel search failed", source)
        return ToolResult(
            ok=False,
            error=ToolError(
                code=f"{source}_hotel_search_exception",
                message=str(exc),
                retryable=True,
                details={"source": source},
            ),
        )


def search_hotels_booking_com(
    city_code: str,
    check_in: date,
    check_out: Optional[date] = None,
    adults: int = 1,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "booking.com"
    check_out = check_out or (check_in + timedelta(days=3))
    label = city_label(city_code)

    def _mock() -> List[HotelOffer]:
        return [
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"{label} Central Suites",
                base_nightly=142,
                rating=4.4,
                address=f"Downtown {label}",
            ),
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Booking Inn {label}",
                base_nightly=98,
                rating=3.9,
                address=f"Midtown {label}",
            ),
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Harbor View {label}",
                base_nightly=186,
                rating=4.7,
                address=f"Waterfront {label}",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


def search_hotels_com(
    city_code: str,
    check_in: date,
    check_out: Optional[date] = None,
    adults: int = 1,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "hotels.com"
    check_out = check_out or (check_in + timedelta(days=3))
    label = city_label(city_code)

    def _mock() -> List[HotelOffer]:
        return [
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Hotels.com Stay {label}",
                base_nightly=119,
                rating=4.1,
                address=f"Union St, {label}",
            ),
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Rewards Lodge {label}",
                base_nightly=156,
                rating=4.5,
                address=f"Park Ave, {label}",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


def search_hotels_expedia(
    city_code: str,
    check_in: date,
    check_out: Optional[date] = None,
    adults: int = 1,
    settings: Optional[Settings] = None,
) -> ToolResult:
    settings = settings or get_settings()
    source = "expedia"
    check_out = check_out or (check_in + timedelta(days=3))
    label = city_label(city_code)

    def _mock() -> List[HotelOffer]:
        return [
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Expedia Select {label}",
                base_nightly=132,
                rating=4.2,
                address=f"Market St, {label}",
            ),
            build_mock_hotel(
                source=source,
                city_code=city_code,
                city_label=label,
                check_in=check_in,
                check_out=check_out,
                name=f"Cityscape Hotel {label}",
                base_nightly=210,
                rating=4.6,
                address=f"Skyline Blvd, {label}",
            ),
        ]

    if settings.flight_sources != "live":
        return _wrap(_mock, source)
    return _wrap(_mock, source)


HOTEL_SITE_TOOLS = {
    "search_hotels_booking_com": search_hotels_booking_com,
    "search_hotels_com": search_hotels_com,
    "search_hotels_expedia": search_hotels_expedia,
}
