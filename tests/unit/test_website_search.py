"""Tests for multi-website search merge, enrichment, and airport lookup."""

from __future__ import annotations

from datetime import date, datetime

from travel_agent.data.airports import airport_coords, pick_layover_hubs, search_airports
from travel_agent.models import FlightOffer, FlightSegment, ToolResult
from travel_agent.tools.websites._mock_helpers import build_mock_flight, enrich_flight_offer
from travel_agent.tools.websites.coordinator import merge_flights
from travel_agent.tools.websites.flight_sources import search_google_flights, search_kayak


def test_airport_search_tokyo_and_heathrow():
    tokyo = search_airports("Tokyo")
    assert any(r.iata in {"NRT", "HND"} for r in tokyo)
    lhr = search_airports("Heathrow")
    assert lhr and lhr[0].iata == "LHR"
    assert lhr[0].lat is not None and lhr[0].lon is not None


def test_airport_coords_known():
    coords = airport_coords("ORD")
    assert coords is not None
    lat, lon = coords
    assert 41 < lat < 43
    assert -89 < lon < -86


def test_merge_flights_dedupes_and_keeps_sources():
    a = search_google_flights("JFK", "LAX", date(2026, 9, 1), adults=1)
    b = search_kayak("JFK", "LAX", date(2026, 9, 1), adults=1)
    merged, errors = merge_flights([a, b])
    assert errors == 0
    assert len(merged) >= 2
    sources = {f.source for f in merged}
    assert "google_flights" in sources or "kayak" in sources


def test_mock_flight_has_numbers_names_and_cabin():
    offer = build_mock_flight(
        source="kayak",
        origin="JFK",
        destination="LAX",
        departure_date=date(2026, 9, 1),
        adults=1,
        carrier="AA",
        stops=1,
        base_price=241,
        price_jitter=-5,
        dep_hour=14,
        flight_no_prefix="AA",
    )
    assert offer.carrier_name == "American Airlines"
    assert offer.origin_name
    assert offer.destination_name
    assert offer.cabin == "ECONOMY"
    assert offer.currency == "USD"
    assert offer.deep_link
    assert offer.stops == 1
    assert len(offer.segments) == 2
    for seg in offer.segments:
        assert seg.flight_number and " " in seg.flight_number
        assert seg.origin_name and seg.destination_name
        assert seg.duration
        assert seg.aircraft
        assert seg.carrier_name


def test_layover_consistency_times_add_up():
    offer = build_mock_flight(
        source="google_flights",
        origin="JFK",
        destination="LAX",
        departure_date=date(2026, 10, 12),
        adults=2,
        carrier="UA",
        stops=1,
        base_price=268,
        price_jitter=0,
        dep_hour=11,
        flight_no_prefix="UA",
    )
    assert len(offer.layovers) == 1
    lay = offer.layovers[0]
    assert lay.airport not in {offer.origin, offer.destination}
    assert lay.duration_minutes >= 45
    assert lay.airport_name

    # Segment chain is contiguous with layover gap
    s0, s1 = offer.segments
    assert s0.destination == s1.origin == lay.airport
    arr0 = datetime.fromisoformat(s0.arrival_at)
    dep1 = datetime.fromisoformat(s1.departure_at)
    gap = int((dep1 - arr0).total_seconds() // 60)
    assert gap == lay.duration_minutes

    # Total duration matches first dep → last arr
    first = datetime.fromisoformat(offer.departure_at)
    last = datetime.fromisoformat(offer.arrival_at)
    total = int((last - first).total_seconds() // 60)
    assert offer.duration.startswith("PT")
    # Parse PT#H#M
    import re

    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", offer.duration)
    assert m
    parsed = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    assert parsed == total


def test_two_stop_hubs_are_realistic():
    hubs = pick_layover_hubs("JFK", "LAX", stops=2, carrier="AA", seed=42)
    assert len(hubs) == 2
    assert "JFK" not in hubs and "LAX" not in hubs
    offer = build_mock_flight(
        source="kayak",
        origin="JFK",
        destination="LAX",
        departure_date=date(2026, 11, 3),
        adults=1,
        carrier="AA",
        stops=2,
        base_price=241,
        price_jitter=-5,
        dep_hour=14,
        flight_no_prefix="AA",
    )
    assert offer.stops == 2
    assert len(offer.segments) == 3
    assert len(offer.layovers) == 2
    assert offer.segments[0].origin == "JFK"
    assert offer.segments[-1].destination == "LAX"


def test_enrich_flight_offer_fills_sparse_live_shape():
    sparse = FlightOffer(
        offer_id="live-1",
        source="kayak",
        carrier="DL",
        origin="JFK",
        destination="CDG",
        departure_at="2026-09-01T08:00:00",
        arrival_at="2026-09-01T20:30:00",
        duration="PT12H30M",
        stops=0,
        segments=[
            FlightSegment(
                origin="JFK",
                destination="CDG",
                departure_at="2026-09-01T08:00:00",
                arrival_at="2026-09-01T20:30:00",
                carrier="DL",
                flight_number="DL421",
            )
        ],
        price_usd=799.0,
        raw={"mock": False},
    )
    rich = enrich_flight_offer(sparse)
    assert rich.carrier_name == "Delta Air Lines"
    assert rich.origin_name and "Kennedy" in rich.origin_name
    assert rich.segments[0].flight_number == "DL 421"
    assert rich.segments[0].duration
    assert rich.deep_link
    assert rich.cabin == "ECONOMY"
