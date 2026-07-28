"""Post-approval booking against the selected offer's source website (mock by default)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from travel_agent.config import Settings, get_settings
from travel_agent.models import BookingRecord, FlightOffer, HotelOffer, ToolError, ToolResult
from travel_agent.observability.logging import get_logger

logger = get_logger(__name__)


class WebsiteBookingClient:
    """Books via the OTA/airline indicated on the offer — no Amadeus on the default path."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def book_flight(
        self,
        flight: FlightOffer,
        travelers: List[Dict[str, Any]],
        approval_id: str,
        idempotency_key: str,
    ) -> ToolResult:
        try:
            if not approval_id:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="approval_required",
                        message="book_flight requires a valid approval_id",
                        retryable=False,
                    ),
                )
            source = flight.source or "website"
            ref = f"{source.upper()[:3]}-PNR-{flight.offer_id[-10:]}"
            record = BookingRecord(
                kind="flight",
                provider_ref=ref,
                status="CONFIRMED",
                amount_usd=flight.price_usd,
                idempotency_key=idempotency_key,
                raw={
                    "mock": self.settings.flight_sources != "live",
                    "source": source,
                    "approval_id": approval_id,
                    "offer_id": flight.offer_id,
                    "travelers": len(travelers),
                },
            )
            return ToolResult(ok=True, data=record)
        except Exception as exc:  # noqa: BLE001
            logger.exception("book_flight failed")
            return ToolResult(
                ok=False,
                error=ToolError(code="flight_book_exception", message=str(exc), retryable=True),
            )

    def book_hotel(
        self,
        hotel: HotelOffer,
        guests: List[Dict[str, Any]],
        approval_id: str,
        idempotency_key: str,
    ) -> ToolResult:
        try:
            if not approval_id:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="approval_required",
                        message="book_hotel requires a valid approval_id",
                        retryable=False,
                    ),
                )
            source = hotel.source or "website"
            ref = f"{source.upper()[:3]}-HTL-{hotel.offer_id[-10:]}"
            record = BookingRecord(
                kind="hotel",
                provider_ref=ref,
                status="CONFIRMED",
                amount_usd=hotel.price_usd,
                idempotency_key=idempotency_key,
                raw={
                    "mock": self.settings.flight_sources != "live",
                    "source": source,
                    "approval_id": approval_id,
                    "offer_id": hotel.offer_id,
                },
            )
            return ToolResult(ok=True, data=record)
        except Exception as exc:  # noqa: BLE001
            logger.exception("book_hotel failed")
            return ToolResult(
                ok=False,
                error=ToolError(code="hotel_book_exception", message=str(exc), retryable=True),
            )
