"""Merge, dedupe, and rank multi-source flight and hotel offers."""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from travel_agent.models.schemas import FlightOffer, HotelOffer, ToolResult
from travel_agent.tools.websites._mock_helpers import enrich_flight_offer


def _flight_dedupe_key(f: FlightOffer) -> str:
    dep = f.departure_at[:16] if f.departure_at else ""
    nums = "|".join(s.flight_number or "" for s in (f.segments or [])[:3])
    return f"{f.carrier}|{f.origin}|{f.destination}|{dep}|{nums}|{round(f.price_usd)}"


def merge_flights(results: List[ToolResult]) -> Tuple[List[FlightOffer], int]:
    """Combine flight lists; keep cheapest per dedupe key, preserve source diversity."""
    by_key: Dict[str, FlightOffer] = {}
    errors = 0
    for res in results:
        if not res.ok:
            errors += 1
            continue
        for offer in res.data or []:
            if not isinstance(offer, FlightOffer):
                offer = FlightOffer.model_validate(offer)
            offer = enrich_flight_offer(offer)
            key = _flight_dedupe_key(offer)
            prev = by_key.get(key)
            if prev is None or offer.price_usd < prev.price_usd:
                by_key[key] = offer
    ranked = rank_flights(list(by_key.values()))
    return ranked, errors


def rank_flights(offers: List[FlightOffer]) -> List[FlightOffer]:
    def score(f: FlightOffer) -> Tuple[float, float, float]:
        return (f.price_usd, float(f.stops), -len(f.segments))

    return sorted(offers, key=score)


def _hotel_dedupe_key(h: HotelOffer) -> str:
    return f"{h.name.lower()}|{h.check_in}|{h.check_out}"


def merge_hotels(results: List[ToolResult]) -> Tuple[List[HotelOffer], int]:
    by_key: Dict[str, HotelOffer] = {}
    errors = 0
    for res in results:
        if not res.ok:
            errors += 1
            continue
        for offer in res.data or []:
            if not isinstance(offer, HotelOffer):
                offer = HotelOffer.model_validate(offer)
            key = _hotel_dedupe_key(offer)
            prev = by_key.get(key)
            if prev is None or offer.price_usd < prev.price_usd:
                by_key[key] = offer
    ranked = rank_hotels(list(by_key.values()))
    return ranked, errors


def rank_hotels(offers: List[HotelOffer]) -> List[HotelOffer]:
    def score(h: HotelOffer) -> Tuple[float, float]:
        rating = h.rating if h.rating is not None else 3.5
        return (h.price_usd, -rating)

    return sorted(offers, key=score)


class MultiSourceSearchCoordinator:
    """Runs registered website search tools and merges results."""

    def __init__(
        self,
        flight_tools: Dict[str, Callable[..., ToolResult]] | None = None,
        hotel_tools: Dict[str, Callable[..., ToolResult]] | None = None,
    ):
        from travel_agent.tools.websites.flight_sources import FLIGHT_SITE_TOOLS
        from travel_agent.tools.websites.hotel_sources import HOTEL_SITE_TOOLS

        self.flight_tools = flight_tools or FLIGHT_SITE_TOOLS
        self.hotel_tools = hotel_tools or HOTEL_SITE_TOOLS

    def flight_tool_specs(self) -> List[str]:
        return list(self.flight_tools.keys())

    def hotel_tool_specs(self) -> List[str]:
        return list(self.hotel_tools.keys())

    def run_flight_tool(self, name: str, **kwargs) -> ToolResult:
        fn = self.flight_tools[name]
        return fn(**kwargs)

    def run_hotel_tool(self, name: str, **kwargs) -> ToolResult:
        fn = self.hotel_tools[name]
        return fn(**kwargs)

    def merge_flight_results(self, results: List[ToolResult]) -> Tuple[List[FlightOffer], int]:
        return merge_flights(results)

    def merge_hotel_results(self, results: List[ToolResult]) -> Tuple[List[HotelOffer], int]:
        return merge_hotels(results)
