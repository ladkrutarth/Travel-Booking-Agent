"""Deterministic budget filtering and scoring."""

from __future__ import annotations

from typing import List, Optional, Tuple

from travel_agent.models import FlightOffer, HotelOffer, ProposedItinerary


def total_cost(flight: Optional[FlightOffer], hotel: Optional[HotelOffer]) -> float:
    return float((flight.price_usd if flight else 0.0) + (hotel.price_usd if hotel else 0.0))


def filter_within_budget(
    flights: List[FlightOffer],
    hotels: List[HotelOffer],
    budget_usd: Optional[float],
) -> List[Tuple[FlightOffer, HotelOffer, float]]:
    """Return flight+hotel pairs sorted by total ascending, filtered by budget when set."""
    pairs: List[Tuple[FlightOffer, HotelOffer, float]] = []
    for flight in flights:
        for hotel in hotels:
            cost = total_cost(flight, hotel)
            if budget_usd is not None and cost > budget_usd:
                continue
            pairs.append((flight, hotel, cost))
    pairs.sort(key=lambda p: p[2])
    return pairs


def score_itinerary(
    proposal: ProposedItinerary,
    *,
    prefer_direct: bool = True,
    prefer_rating: bool = True,
) -> float:
    """Higher is better. Pure heuristic for ranking."""
    score = 0.0
    if proposal.within_budget:
        score += 50.0
    score -= proposal.total_usd / 50.0
    if proposal.flight and prefer_direct and proposal.flight.stops == 0:
        score += 15.0
    if proposal.hotel and prefer_rating and proposal.hotel.rating:
        score += proposal.hotel.rating * 3.0
    if proposal.reviews and proposal.reviews.rating:
        score += proposal.reviews.rating * 2.0
    return score
