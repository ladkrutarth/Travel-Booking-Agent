"""Unit tests for Amadeus mock tool wrappers."""

from __future__ import annotations

from datetime import date

from travel_agent.config import Settings
from travel_agent.models import FlightOffer
from travel_agent.tools.amadeus import AmadeusClient


def test_mock_search_and_book_requires_approval():
    client = AmadeusClient(Settings(amadeus_mock=True))
    flights = client.search_flights("JFK", "LAX", date(2026, 8, 1), adults=1)
    assert flights.ok
    assert len(flights.data) >= 1
    flight: FlightOffer = flights.data[0]

    denied = client.book_flight(flight, travelers=[], approval_id="", idempotency_key="k1")
    assert not denied.ok
    assert denied.error.code == "approval_required"

    booked = client.book_flight(
        flight, travelers=[], approval_id="apr-1", idempotency_key="k2"
    )
    assert booked.ok
    assert booked.data.status == "CONFIRMED"
