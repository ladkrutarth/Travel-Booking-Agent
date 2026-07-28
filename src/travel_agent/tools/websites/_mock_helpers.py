"""Shared mock offer builders for OTA-style website adapters."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence
from urllib.parse import quote

from travel_agent.data.airports import (
    airport_city,
    airport_name,
    carrier_display_name,
    estimate_block_minutes,
    pick_layover_hubs,
)
from travel_agent.models import FlightOffer, FlightSegment, HotelOffer, LayoverInfo

_AIRCRAFT_BY_CARRIER = {
    "AA": ["B738", "A321", "B772", "A319"],
    "UA": ["B738", "B739", "B777", "A320"],
    "DL": ["B738", "A321", "A339", "B752"],
    "B6": ["A320", "A321", "A220"],
    "AS": ["B739", "A320", "E175"],
    "WN": ["B738", "B737", "B38M"],
    "BA": ["A320", "B777", "A350", "B787"],
    "AF": ["A320", "A350", "B777", "A318"],
    "LH": ["A320", "A321", "A343", "B748"],
    "KL": ["B737", "A330", "B787"],
    "EK": ["A380", "B777", "A350"],
    "QR": ["A350", "B777", "A320"],
    "SQ": ["A350", "B787", "A380"],
    "AC": ["B789", "A321", "A333"],
    "IB": ["A320", "A350", "A333"],
    "LX": ["A320", "A321", "B777"],
    "TK": ["A321", "B777", "A350"],
    "EY": ["A321", "B787", "A380"],
}

_SOURCE_DEEP_LINKS = {
    "google_flights": "https://www.google.com/travel/flights",
    "kayak": "https://www.kayak.com/flights",
    "expedia": "https://www.expedia.com/Flights",
    "booking.com": "https://www.booking.com/flights",
    "airline_direct": "https://www.airline-direct.example/book",
}


def _seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


def _iso_at(d: date, hour: int, minute: int = 0) -> str:
    return datetime(d.year, d.month, d.day, hour, minute).isoformat()


def _duration_hm(total_minutes: int) -> str:
    total_minutes = max(0, int(total_minutes))
    h, m = divmod(total_minutes, 60)
    return f"PT{h}H{m}M" if m else f"PT{h}H"


def _parse_duration_minutes(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    import re

    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", value)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _format_flight_number(prefix: str, number: int) -> str:
    code = (prefix or "XX").upper().strip()
    # Keep IATA-style "AA 100"
    digits = "".join(ch for ch in code if ch.isdigit())
    letters = "".join(ch for ch in code if ch.isalpha()) or "XX"
    if digits:
        return f"{letters} {digits}"
    return f"{letters} {number}"


def _pick_aircraft(carrier: str, seed: int, long_haul: bool) -> str:
    fleet = _AIRCRAFT_BY_CARRIER.get(carrier.upper(), ["A320", "B738", "B777"])
    if long_haul:
        wide = [a for a in fleet if a.startswith(("B77", "B78", "A33", "A34", "A35", "A38"))]
        if wide:
            return wide[seed % len(wide)]
    return fleet[seed % len(fleet)]


def _deep_link(source: str, origin: str, destination: str, departure_date: date) -> str:
    base = _SOURCE_DEEP_LINKS.get(source, f"https://example.com/{quote(source)}")
    return f"{base}?from={origin}&to={destination}&date={departure_date.isoformat()}&mock=1"


def _build_layovers(segments: Sequence[FlightSegment]) -> List[LayoverInfo]:
    layovers: List[LayoverInfo] = []
    for i in range(len(segments) - 1):
        arr = datetime.fromisoformat(segments[i].arrival_at)
        dep = datetime.fromisoformat(segments[i + 1].departure_at)
        mins = max(0, int((dep - arr).total_seconds() // 60))
        ap = segments[i].destination
        layovers.append(
            LayoverInfo(
                airport=ap,
                airport_name=segments[i].destination_name or airport_name(ap),
                city=airport_city(ap),
                duration_minutes=mins,
            )
        )
    return layovers


def enrich_flight_offer(offer: FlightOffer) -> FlightOffer:
    """Fill missing names, durations, layovers, and cabin for mock or sparse live offers."""
    carrier = (offer.carrier or "").upper()
    carrier_name = offer.carrier_name or carrier_display_name(carrier)
    origin_name = offer.origin_name or airport_name(offer.origin)
    destination_name = offer.destination_name or airport_name(offer.destination)
    cabin = offer.cabin or (offer.raw or {}).get("cabin") or "ECONOMY"

    segments: List[FlightSegment] = []
    for i, seg in enumerate(offer.segments or []):
        seg_carrier = (seg.carrier or carrier).upper()
        dep = datetime.fromisoformat(seg.departure_at)
        arr = datetime.fromisoformat(seg.arrival_at)
        dur_min = _parse_duration_minutes(seg.duration)
        if dur_min is None:
            dur_min = max(0, int((arr - dep).total_seconds() // 60))
        fn = seg.flight_number
        if fn and " " not in fn and len(fn) > 2:
            # Normalize "AA100" -> "AA 100"
            letters = "".join(ch for ch in fn if ch.isalpha())
            digits = "".join(ch for ch in fn if ch.isdigit())
            if letters and digits:
                fn = f"{letters} {digits}"
        segments.append(
            FlightSegment(
                origin=seg.origin,
                origin_name=seg.origin_name or airport_name(seg.origin),
                destination=seg.destination,
                destination_name=seg.destination_name or airport_name(seg.destination),
                departure_at=seg.departure_at,
                arrival_at=seg.arrival_at,
                duration=seg.duration or _duration_hm(dur_min),
                carrier=seg_carrier,
                carrier_name=seg.carrier_name or carrier_display_name(seg_carrier),
                flight_number=fn,
                aircraft=seg.aircraft,
                cabin=seg.cabin or cabin,
                layover_city=seg.layover_city,
            )
        )

    if not segments:
        # Synthesize a single segment from offer-level fields
        block = estimate_block_minutes(offer.origin, offer.destination)
        segments = [
            FlightSegment(
                origin=offer.origin,
                origin_name=origin_name,
                destination=offer.destination,
                destination_name=destination_name,
                departure_at=offer.departure_at,
                arrival_at=offer.arrival_at,
                duration=offer.duration or _duration_hm(block),
                carrier=carrier,
                carrier_name=carrier_name,
                flight_number=offer.raw.get("flight_number") if offer.raw else None,
                cabin=cabin,
            )
        ]

    layovers = list(offer.layovers) if offer.layovers else _build_layovers(segments)
    stops = offer.stops if offer.stops is not None else max(0, len(segments) - 1)
    if stops == 0 and len(segments) > 1:
        stops = len(segments) - 1

    # Recompute total duration from first dep to last arr when possible
    total_duration = offer.duration
    try:
        first = datetime.fromisoformat(segments[0].departure_at)
        last = datetime.fromisoformat(segments[-1].arrival_at)
        total_duration = _duration_hm(int((last - first).total_seconds() // 60))
    except (TypeError, ValueError):
        pass

    deep_link = offer.deep_link
    if not deep_link and offer.source:
        try:
            dep_date = date.fromisoformat(offer.departure_at[:10])
            deep_link = _deep_link(offer.source, offer.origin, offer.destination, dep_date)
        except ValueError:
            deep_link = None

    raw = dict(offer.raw or {})
    raw.setdefault("cabin", cabin)
    raw.setdefault("label", "Nonstop" if stops == 0 else f"{stops}-stop")
    raw.setdefault("mock", raw.get("mock", False))

    return offer.model_copy(
        update={
            "carrier": carrier,
            "carrier_name": carrier_name,
            "origin_name": origin_name,
            "destination_name": destination_name,
            "duration": total_duration,
            "stops": stops,
            "segments": segments,
            "layovers": layovers,
            "cabin": cabin,
            "currency": offer.currency or "USD",
            "deep_link": deep_link,
            "raw": raw,
        }
    )


def build_mock_flight(
    *,
    source: str,
    origin: str,
    destination: str,
    departure_date: date,
    adults: int,
    carrier: str,
    stops: int,
    base_price: float,
    price_jitter: float,
    dep_hour: int,
    flight_no_prefix: str,
    cabin: str = "ECONOMY",
) -> FlightOffer:
    origin = origin.upper().strip()
    destination = destination.upper().strip()
    carrier = carrier.upper().strip()
    seed = _seed(source, origin, destination, departure_date.isoformat(), carrier, str(stops))
    jitter = (seed % 47) - 23
    # Source-specific variance still looks plausible (± modest band around base)
    source_bias = {
        "google_flights": -8,
        "kayak": 5,
        "expedia": 12,
        "booking.com": 3,
        "airline_direct": -15,
    }.get(source, 0)
    price = round(max(89.0, (base_price + price_jitter + source_bias + jitter * 3.5) * adults), 2)

    dep_minute = (seed % 50)
    dep_dt = datetime(departure_date.year, departure_date.month, departure_date.day, dep_hour, dep_minute)
    hubs = pick_layover_hubs(origin, destination, stops, carrier, seed)
    waypoints = [origin, *hubs, destination]

    segments: List[FlightSegment] = []
    cursor = dep_dt
    for i in range(len(waypoints) - 1):
        seg_from, seg_to = waypoints[i], waypoints[i + 1]
        block = estimate_block_minutes(seg_from, seg_to)
        # small deterministic variance so same route isn't identical every time
        block += (seed + i * 17) % 25 - 8
        block = max(55, block)
        long_haul = block >= 360
        aircraft = _pick_aircraft(carrier, seed + i, long_haul)
        flight_no = _format_flight_number(flight_no_prefix, 100 + (seed % 800) + i * 37)
        seg_dep = cursor
        seg_arr = seg_dep + timedelta(minutes=block)
        segments.append(
            FlightSegment(
                origin=seg_from,
                origin_name=airport_name(seg_from),
                destination=seg_to,
                destination_name=airport_name(seg_to),
                departure_at=seg_dep.isoformat(),
                arrival_at=seg_arr.isoformat(),
                duration=_duration_hm(block),
                carrier=carrier,
                carrier_name=carrier_display_name(carrier),
                flight_number=flight_no,
                aircraft=aircraft,
                cabin=cabin,
                layover_city=seg_from if i > 0 else None,
            )
        )
        if i < len(waypoints) - 2:
            layover_min = 55 + (seed + i * 13) % 85  # 55–139 min
            cursor = seg_arr + timedelta(minutes=layover_min)
        else:
            cursor = seg_arr

    layovers = _build_layovers(segments)
    total_min = int(
        (datetime.fromisoformat(segments[-1].arrival_at) - datetime.fromisoformat(segments[0].departure_at)).total_seconds()
        // 60
    )
    offer_id = (
        f"{source[:3]}-{carrier}-{origin}{destination}-{departure_date.isoformat()}-{stops}-{seed % 10000}"
    )
    label = "Nonstop" if stops == 0 else f"{stops}-stop"
    offer = FlightOffer(
        offer_id=offer_id,
        source=source,
        carrier=carrier,
        carrier_name=carrier_display_name(carrier),
        origin=origin,
        origin_name=airport_name(origin),
        destination=destination,
        destination_name=airport_name(destination),
        departure_at=segments[0].departure_at,
        arrival_at=segments[-1].arrival_at,
        duration=_duration_hm(total_min),
        stops=stops,
        segments=segments,
        layovers=layovers,
        cabin=cabin,
        price_usd=price,
        currency="USD",
        deep_link=_deep_link(source, origin, destination, departure_date),
        raw={
            "source": source,
            "label": label,
            "cabin": cabin,
            "mock": True,
            "adults": adults,
            "flight_numbers": [s.flight_number for s in segments],
        },
    )
    return enrich_flight_offer(offer)


def build_mock_hotel(
    *,
    source: str,
    city_code: str,
    city_label: str,
    check_in: date,
    check_out: date,
    name: str,
    base_nightly: float,
    rating: float,
    address: str,
) -> HotelOffer:
    nights = max(1, (check_out - check_in).days)
    seed = _seed(source, name, city_code, check_in.isoformat())
    total = round(base_nightly * nights + (seed % 40), 2)
    offer_id = f"{source[:3]}-htl-{hashlib.md5(name.encode()).hexdigest()[:10]}-{seed % 9999}"
    return HotelOffer(
        offer_id=offer_id,
        source=source,
        hotel_id=f"HTL-{seed % 100000}",
        name=name,
        city=city_label or city_code,
        check_in=check_in,
        check_out=check_out,
        price_usd=total,
        currency="USD",
        rating=rating,
        address=address,
        raw={"source": source, "nights": nights, "mock": True},
    )


def city_label(code: str) -> str:
    return airport_city(code)
