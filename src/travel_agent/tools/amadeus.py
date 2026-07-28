"""Amadeus flight and hotel search/booking client."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from travel_agent.config import Settings, get_settings
from travel_agent.models import BookingRecord, FlightOffer, HotelOffer, ToolError, ToolResult
from travel_agent.observability.logging import get_logger

logger = get_logger(__name__)


class AmadeusClient:
    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.Client] = None):
        self.settings = settings or get_settings()
        self._client = client or httpx.Client(timeout=30.0)
        self._token: Optional[str] = None

    def close(self) -> None:
        self._client.close()

    def _mock_flights(
        self, origin: str, destination: str, departure_date: date, adults: int
    ) -> List[FlightOffer]:
        base = 280.0 + (adults - 1) * 220.0
        day = departure_date.isoformat()
        return [
            FlightOffer(
                offer_id=f"mock-flight-aa-direct-{origin}-{destination}",
                carrier="AA",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T08:15:00",
                arrival_at=f"{day}T11:45:00",
                duration="PT3H30M",
                stops=0,
                price_usd=round(base, 2),
                raw={"mock": True, "cabin": "ECONOMY", "label": "Morning nonstop"},
            ),
            FlightOffer(
                offer_id=f"mock-flight-dl-direct-{origin}-{destination}",
                carrier="DL",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T13:40:00",
                arrival_at=f"{day}T17:05:00",
                duration="PT3H25M",
                stops=0,
                price_usd=round(base * 1.08, 2),
                raw={"mock": True, "cabin": "ECONOMY", "label": "Afternoon nonstop"},
            ),
            FlightOffer(
                offer_id=f"mock-flight-ua-1stop-{origin}-{destination}",
                carrier="UA",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T06:00:00",
                arrival_at=f"{day}T14:20:00",
                duration="PT8H20M",
                stops=1,
                price_usd=round(base * 0.82, 2),
                raw={"mock": True, "cabin": "ECONOMY", "label": "Value 1-stop"},
            ),
            FlightOffer(
                offer_id=f"mock-flight-b6-redeye-{origin}-{destination}",
                carrier="B6",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T22:10:00",
                arrival_at=f"{(departure_date + timedelta(days=1)).isoformat()}T01:35:00",
                duration="PT3H25M",
                stops=0,
                price_usd=round(base * 0.74, 2),
                raw={"mock": True, "cabin": "ECONOMY", "label": "Red-eye saver"},
            ),
            FlightOffer(
                offer_id=f"mock-flight-as-premium-{origin}-{destination}",
                carrier="AS",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T10:05:00",
                arrival_at=f"{day}T13:40:00",
                duration="PT3H35M",
                stops=0,
                price_usd=round(base * 1.35, 2),
                raw={"mock": True, "cabin": "PREMIUM_ECONOMY", "label": "Premium economy"},
            ),
            FlightOffer(
                offer_id=f"mock-flight-nk-2stop-{origin}-{destination}",
                carrier="NK",
                origin=origin,
                destination=destination,
                departure_at=f"{day}T05:20:00",
                arrival_at=f"{day}T16:50:00",
                duration="PT11H30M",
                stops=2,
                price_usd=round(base * 0.61, 2),
                raw={"mock": True, "cabin": "ECONOMY", "label": "Cheapest multi-stop"},
            ),
        ]

    def _mock_hotels(
        self, city: str, check_in: date, check_out: date
    ) -> List[HotelOffer]:
        nights = max((check_out - check_in).days, 1)
        return [
            HotelOffer(
                offer_id="mock-hotel-downtown",
                hotel_id="MOCKHTL1",
                name=f"{city.title()} Downtown Inn",
                city=city,
                check_in=check_in,
                check_out=check_out,
                price_usd=round(145.0 * nights, 2),
                rating=4.2,
                address="100 Main St",
                raw={"mock": True},
            ),
            HotelOffer(
                offer_id="mock-hotel-boutique",
                hotel_id="MOCKHTL2",
                name=f"{city.title()} Boutique Hotel",
                city=city,
                check_in=check_in,
                check_out=check_out,
                price_usd=round(210.0 * nights, 2),
                rating=4.7,
                address="42 Harbor Ave",
                raw={"mock": True},
            ),
            HotelOffer(
                offer_id="mock-hotel-airport",
                hotel_id="MOCKHTL3",
                name=f"{city.title()} Airport Lodge",
                city=city,
                check_in=check_in,
                check_out=check_out,
                price_usd=round(98.0 * nights, 2),
                rating=3.8,
                address="1 Terminal Rd",
                raw={"mock": True},
            ),
            HotelOffer(
                offer_id="mock-hotel-resort",
                hotel_id="MOCKHTL4",
                name=f"{city.title()} Waterfront Resort",
                city=city,
                check_in=check_in,
                check_out=check_out,
                price_usd=round(289.0 * nights, 2),
                rating=4.9,
                address="8 Bayfront Blvd",
                raw={"mock": True},
            ),
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    def _authenticate(self) -> str:
        if self._token:
            return self._token
        if not self.settings.amadeus_client_id or not self.settings.amadeus_client_secret:
            raise RuntimeError("Amadeus credentials missing")
        resp = self._client.post(
            f"{self.settings.amadeus_base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.amadeus_client_id,
                "client_secret": self.settings.amadeus_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._authenticate()}"}

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        adults: int = 1,
        return_date: Optional[date] = None,
        max_results: int = 5,
    ) -> ToolResult:
        try:
            if self.settings.amadeus_mock:
                offers = self._mock_flights(origin, destination, departure_date, adults)
                return ToolResult(ok=True, data=offers[:max_results])

            params: Dict[str, Any] = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date.isoformat(),
                "adults": adults,
                "currencyCode": "USD",
                "max": max_results,
            }
            if return_date:
                params["returnDate"] = return_date.isoformat()

            resp = self._client.get(
                f"{self.settings.amadeus_base_url}/v2/shopping/flight-offers",
                params=params,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_flight_search_failed",
                        message=resp.text,
                        retryable=resp.status_code >= 500,
                        details={"status": resp.status_code},
                    ),
                )
            data = resp.json().get("data", [])
            offers: List[FlightOffer] = []
            for item in data:
                itineraries = item.get("itineraries", [])
                segments = itineraries[0]["segments"] if itineraries else []
                first, last = segments[0], segments[-1]
                price = float(item.get("price", {}).get("total", 0))
                offers.append(
                    FlightOffer(
                        offer_id=item.get("id", ""),
                        carrier=first.get("carrierCode", "?"),
                        origin=first.get("departure", {}).get("iataCode", origin),
                        destination=last.get("arrival", {}).get("iataCode", destination),
                        departure_at=first.get("departure", {}).get("at", ""),
                        arrival_at=last.get("arrival", {}).get("at", ""),
                        duration=itineraries[0].get("duration", "") if itineraries else "",
                        stops=max(len(segments) - 1, 0),
                        price_usd=price,
                        currency=item.get("price", {}).get("currency", "USD"),
                        raw=item,
                    )
                )
            return ToolResult(ok=True, data=offers)
        except Exception as exc:  # noqa: BLE001 — surface as structured tool error
            logger.exception("search_flights failed")
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="amadeus_flight_search_exception",
                    message=str(exc),
                    retryable=True,
                ),
            )

    def search_hotels(
        self,
        city_code: str,
        check_in: date,
        check_out: Optional[date] = None,
        adults: int = 1,
        max_results: int = 5,
    ) -> ToolResult:
        try:
            check_out = check_out or (check_in + timedelta(days=2))
            if self.settings.amadeus_mock:
                offers = self._mock_hotels(city_code, check_in, check_out)
                return ToolResult(ok=True, data=offers[:max_results])

            # Resolve city -> hotel IDs then offers (simplified Amadeus hotel flow)
            list_resp = self._client.get(
                f"{self.settings.amadeus_base_url}/v1/reference-data/locations/hotels/by-city",
                params={"cityCode": city_code},
                headers=self._headers(),
            )
            if list_resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_hotel_list_failed",
                        message=list_resp.text,
                        retryable=list_resp.status_code >= 500,
                    ),
                )
            hotel_ids = [h["hotelId"] for h in list_resp.json().get("data", [])[:20]]
            if not hotel_ids:
                return ToolResult(ok=True, data=[])

            offers_resp = self._client.get(
                f"{self.settings.amadeus_base_url}/v3/shopping/hotel-offers",
                params={
                    "hotelIds": ",".join(hotel_ids[:10]),
                    "adults": adults,
                    "checkInDate": check_in.isoformat(),
                    "checkOutDate": check_out.isoformat(),
                    "currency": "USD",
                },
                headers=self._headers(),
            )
            if offers_resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_hotel_search_failed",
                        message=offers_resp.text,
                        retryable=offers_resp.status_code >= 500,
                    ),
                )
            offers: List[HotelOffer] = []
            for item in offers_resp.json().get("data", [])[:max_results]:
                hotel = item.get("hotel", {})
                offer = (item.get("offers") or [{}])[0]
                price = float(offer.get("price", {}).get("total", 0))
                offers.append(
                    HotelOffer(
                        offer_id=offer.get("id", hotel.get("hotelId", "")),
                        hotel_id=hotel.get("hotelId", ""),
                        name=hotel.get("name", "Hotel"),
                        city=city_code,
                        check_in=check_in,
                        check_out=check_out,
                        price_usd=price,
                        rating=None,
                        address=(hotel.get("address") or {}).get("lines", [None])[0],
                        raw=item,
                    )
                )
            return ToolResult(ok=True, data=offers)
        except Exception as exc:  # noqa: BLE001
            logger.exception("search_hotels failed")
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="amadeus_hotel_search_exception",
                    message=str(exc),
                    retryable=True,
                ),
            )

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
            if self.settings.amadeus_mock:
                record = BookingRecord(
                    kind="flight",
                    provider_ref=f"MOCK-PNR-{flight.offer_id[-8:]}",
                    status="CONFIRMED",
                    amount_usd=flight.price_usd,
                    idempotency_key=idempotency_key,
                    raw={"mock": True, "approval_id": approval_id, "offer_id": flight.offer_id},
                )
                return ToolResult(ok=True, data=record)

            payload = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [flight.raw or {"id": flight.offer_id}],
                    "travelers": travelers,
                }
            }
            resp = self._client.post(
                f"{self.settings.amadeus_base_url}/v1/booking/flight-orders",
                json=payload,
                headers={**self._headers(), "X-Idempotency-Key": idempotency_key},
            )
            if resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_flight_book_failed",
                        message=resp.text,
                        retryable=False,
                        details={"status": resp.status_code},
                    ),
                )
            body = resp.json().get("data", {})
            record = BookingRecord(
                kind="flight",
                provider_ref=body.get("id", ""),
                status="CONFIRMED",
                amount_usd=flight.price_usd,
                idempotency_key=idempotency_key,
                raw=body,
            )
            return ToolResult(ok=True, data=record)
        except Exception as exc:  # noqa: BLE001
            logger.exception("book_flight failed")
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="amadeus_flight_book_exception",
                    message=str(exc),
                    retryable=True,
                ),
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
            if self.settings.amadeus_mock:
                record = BookingRecord(
                    kind="hotel",
                    provider_ref=f"MOCK-HTL-{hotel.offer_id[-8:]}",
                    status="CONFIRMED",
                    amount_usd=hotel.price_usd,
                    idempotency_key=idempotency_key,
                    raw={"mock": True, "approval_id": approval_id, "offer_id": hotel.offer_id},
                )
                return ToolResult(ok=True, data=record)

            payload = {
                "data": {
                    "offerId": hotel.offer_id,
                    "guests": guests,
                }
            }
            resp = self._client.post(
                f"{self.settings.amadeus_base_url}/v1/booking/hotel-bookings",
                json=payload,
                headers={**self._headers(), "X-Idempotency-Key": idempotency_key},
            )
            if resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_hotel_book_failed",
                        message=resp.text,
                        retryable=False,
                    ),
                )
            body = resp.json().get("data", {})
            # Amadeus may return list
            if isinstance(body, list):
                body = body[0] if body else {}
            record = BookingRecord(
                kind="hotel",
                provider_ref=str(body.get("id", "")),
                status="CONFIRMED",
                amount_usd=hotel.price_usd,
                idempotency_key=idempotency_key,
                raw=body if isinstance(body, dict) else {"data": body},
            )
            return ToolResult(ok=True, data=record)
        except Exception as exc:  # noqa: BLE001
            logger.exception("book_hotel failed")
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="amadeus_hotel_book_exception",
                    message=str(exc),
                    retryable=True,
                ),
            )

    def get_booking_status(self, provider_ref: str) -> ToolResult:
        if self.settings.amadeus_mock:
            return ToolResult(
                ok=True,
                data={"provider_ref": provider_ref, "status": "CONFIRMED", "mock": True},
            )
        try:
            resp = self._client.get(
                f"{self.settings.amadeus_base_url}/v1/booking/flight-orders/{provider_ref}",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="amadeus_status_failed",
                        message=resp.text,
                        retryable=resp.status_code >= 500,
                    ),
                )
            return ToolResult(ok=True, data=resp.json())
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="amadeus_status_exception",
                    message=str(exc),
                    retryable=True,
                ),
            )
