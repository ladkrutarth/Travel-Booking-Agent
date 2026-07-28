"""Trip orchestration: search → select → travelers → approve → book."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from travel_agent.config import Settings, get_settings
from travel_agent.db import UserRow, repository as repo
from travel_agent.errors import AppError
from travel_agent.models import (
    ApprovalRecord,
    BookingRecord,
    FlightOffer,
    HotelOffer,
    ProposedItinerary,
    RankedPair,
    ReviewSummary,
    ToolError,
    ToolResult,
    Traveler,
    TripConstraints,
    TripResponse,
    TripState,
    TripSummary,
    WeatherSummary,
)
from travel_agent.observability import configure_tracing
from travel_agent.observability.logging import get_logger, log_event
from travel_agent.policies.approval import create_approval, stamp_hash, validate_approval_for_booking
from travel_agent.policies.budget import filter_within_budget, score_itinerary, total_cost
from travel_agent.policies.safety import validate_proposal_output
from travel_agent.tools.reviews import ReviewsClient
from travel_agent.tools.weather import WeatherClient
from travel_agent.tools.websites import MultiSourceSearchCoordinator, WebsiteBookingClient

logger = get_logger(__name__)


def _validate_constraints(c: TripConstraints) -> None:
    if not c.origin or len(c.origin) != 3:
        raise AppError(422, "invalid_origin", "Invalid origin", "Origin must be a 3-letter IATA code.")
    if not c.destination or len(c.destination) != 3:
        raise AppError(
            422, "invalid_destination", "Invalid destination", "Destination must be a 3-letter IATA code."
        )
    if not c.departure_date or not c.return_date:
        raise AppError(422, "invalid_dates", "Invalid dates", "Departure and return dates are required.")
    if c.return_date < c.departure_date:
        raise AppError(
            422,
            "invalid_date_range",
            "Invalid date range",
            "Return date must be on or after departure date.",
        )


class TripService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        search_coordinator: Optional[MultiSourceSearchCoordinator] = None,
        booking: Optional[WebsiteBookingClient] = None,
        weather: Optional[WeatherClient] = None,
        reviews: Optional[ReviewsClient] = None,
    ):
        self.settings = settings or get_settings()
        configure_tracing()
        self.search_coordinator = search_coordinator or MultiSourceSearchCoordinator()
        self.booking = booking or WebsiteBookingClient(self.settings)
        self.weather = weather or WeatherClient(self.settings)
        self.reviews = reviews or ReviewsClient(self.settings)

    def _owned(self, session: Session, trip_id: str, user: UserRow):
        row = repo.get_user_trip(session, trip_id, user.id)
        if row is None:
            raise AppError(404, "not_found", "Not found", "Trip not found.")
        return row

    def create_trip(
        self,
        session: Session,
        user: UserRow,
        constraints: TripConstraints,
        preferences_text: Optional[str] = None,
    ) -> TripResponse:
        if self.settings.kill_switch:
            raise AppError(
                503,
                "kill_switch",
                "Service unavailable",
                "Booking is temporarily disabled.",
                retryable=True,
            )
        data = constraints.model_copy(deep=True)
        if preferences_text:
            data.preferences_text = preferences_text
            if preferences_text not in data.preferences:
                data.preferences = list(data.preferences) + [preferences_text]
        _validate_constraints(data)
        row = repo.create_trip(session, user.id, data)
        repo.add_audit(session, row.id, "trip_created", {"user_id": user.id})
        repo.update_trip(session, row.id, state=TripState.CONSTRAINTS, clear_error=True)
        return repo.trip_to_response(repo.get_trip(session, row.id))  # type: ignore[arg-type]

    def list_trips(self, session: Session, user: UserRow) -> List[TripSummary]:
        return [repo.trip_to_summary(r) for r in repo.list_user_trips(session, user.id)]

    def get_trip(self, session: Session, user: UserRow, trip_id: str) -> TripResponse:
        row = self._owned(session, trip_id, user)
        resp = repo.trip_to_response(row)
        if (
            resp.state == TripState.AWAIT_APPROVAL
            and row.proposal_expires_at
            and row.proposal_expires_at < datetime.utcnow()
        ):
            repo.update_trip(
                session,
                trip_id,
                state=TripState.EXPIRED,
                error="Proposal expired. Search again.",
                error_code="proposal_expired",
                retryable=True,
            )
            return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]
        return resp

    def search(self, session: Session, user: UserRow, trip_id: str) -> TripResponse:
        if self.settings.kill_switch:
            raise AppError(
                503, "kill_switch", "Service unavailable", "Booking is temporarily disabled.", retryable=True
            )
        row = self._owned(session, trip_id, user)
        c = TripConstraints.model_validate(
            __import__("json").loads(row.constraints_json)
        )
        _validate_constraints(c)
        assert c.origin and c.destination and c.departure_date and c.return_date

        repo.update_trip(session, trip_id, state=TripState.SEARCH, clear_error=True)

        import time

        def _call_tool(name: str, args: dict, fn):
            repo.record_tool_call(
                session,
                trip_id,
                tool=name,
                status="started",
                summary=f"Calling {name}…",
                args=args,
            )
            t0 = time.perf_counter()
            result = fn()
            latency = round((time.perf_counter() - t0) * 1000, 2)
            if result.ok:
                count = len(result.data) if isinstance(result.data, list) else 1
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool=name,
                    status="ok",
                    summary=f"{name} returned {count} result(s)",
                    args=args,
                    latency_ms=latency,
                )
            else:
                err = result.error
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool=name,
                    status="error",
                    summary=(err.message if err else f"{name} failed"),
                    args=args,
                    latency_ms=latency,
                )
            return result

        flight_kwargs = {
            "origin": c.origin,
            "destination": c.destination,
            "departure_date": c.departure_date.isoformat(),
            "return_date": c.return_date.isoformat() if c.return_date else None,
            "adults": c.adults,
        }
        hotel_kwargs = {
            "city_code": c.destination,
            "check_in": c.departure_date.isoformat(),
            "check_out": c.return_date.isoformat() if c.return_date else None,
            "adults": c.adults,
        }

        def _run_site_tool(name: str, args: dict, fn):
            t0 = time.perf_counter()
            result = fn()
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return name, args, result, latency

        def _record_site_result(name: str, args: dict, result: ToolResult, latency: float):
            if result.ok:
                count = len(result.data) if isinstance(result.data, list) else 1
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool=name,
                    status="ok",
                    summary=f"{name} returned {count} result(s)",
                    args=args,
                    latency_ms=latency,
                )
            else:
                err = result.error
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool=name,
                    status="error",
                    summary=(err.message if err else f"{name} failed"),
                    args=args,
                    latency_ms=latency,
                )

        flight_site_results: List[ToolResult] = []
        hotel_site_results: List[ToolResult] = []
        pending_jobs = []
        for name in self.search_coordinator.flight_tool_specs():
            pending_jobs.append(
                (
                    name,
                    flight_kwargs,
                    lambda n=name: self.search_coordinator.run_flight_tool(
                        n,
                        origin=c.origin,
                        destination=c.destination,
                        departure_date=c.departure_date,
                        adults=c.adults,
                        return_date=c.return_date,
                        settings=self.settings,
                    ),
                    True,
                )
            )
        for name in self.search_coordinator.hotel_tool_specs():
            pending_jobs.append(
                (
                    name,
                    hotel_kwargs,
                    lambda n=name: self.search_coordinator.run_hotel_tool(
                        n,
                        city_code=c.destination,
                        check_in=c.departure_date,
                        check_out=c.return_date,
                        adults=c.adults,
                        settings=self.settings,
                    ),
                    False,
                )
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {
                pool.submit(_run_site_tool, name, args, fn): is_flight
                for name, args, fn, is_flight in pending_jobs
            }
            for fut in as_completed(futs):
                name, args, result, latency = fut.result()
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool=name,
                    status="started",
                    summary=f"Calling {name}…",
                    args=args,
                )
                _record_site_result(name, args, result, latency)
                if futs[fut]:
                    flight_site_results.append(result)
                else:
                    hotel_site_results.append(result)

        flights, flight_errors = self.search_coordinator.merge_flight_results(flight_site_results)
        hotels, hotel_errors = self.search_coordinator.merge_hotel_results(hotel_site_results)
        flight_res = ToolResult(ok=True, data=flights) if flights else ToolResult(
            ok=False,
            error=ToolError(
                code="flight_search_failed",
                message="No flight offers from any website",
                retryable=flight_errors > 0,
            ),
        )
        hotel_res = ToolResult(ok=True, data=hotels) if hotels else ToolResult(
            ok=False,
            error=ToolError(
                code="hotel_search_failed",
                message="No hotel offers from any website",
                retryable=hotel_errors > 0,
            ),
        )
        weather_res = _call_tool(
            "get_weather",
            {
                "location": c.destination_city or c.destination,
                "start": c.departure_date.isoformat(),
                "end": c.return_date.isoformat() if c.return_date else None,
            },
            lambda: self.weather.get_weather(
                c.destination_city or c.destination,
                start_date=c.departure_date,
                end_date=c.return_date,
            ),
        )
        reviews_res = _call_tool(
            "get_reviews",
            {"place_name": c.destination_city or c.destination},
            lambda: self.reviews.get_reviews(
                place_name=c.destination_city or c.destination,
                location=c.destination_city,
            ),
        )

        if not flight_res.ok:
            err = flight_res.error
            repo.update_trip(
                session,
                trip_id,
                state=TripState.FAILED,
                error=err.message if err else "Flight search failed",
                error_code=err.code if err else "flight_search_failed",
                retryable=bool(err.retryable) if err else True,
            )
            raise AppError(
                502,
                err.code if err else "flight_search_failed",
                "Flight search failed",
                err.message if err else "Flight search failed",
                retryable=bool(err.retryable) if err else True,
            )
        if not hotel_res.ok:
            err = hotel_res.error
            repo.update_trip(
                session,
                trip_id,
                state=TripState.FAILED,
                error=err.message if err else "Hotel search failed",
                error_code=err.code if err else "hotel_search_failed",
                retryable=bool(err.retryable) if err else True,
            )
            raise AppError(
                502,
                err.code if err else "hotel_search_failed",
                "Hotel search failed",
                err.message if err else "Hotel search failed",
                retryable=bool(err.retryable) if err else True,
            )

        flights: List[FlightOffer] = list(flight_res.data or [])
        hotels: List[HotelOffer] = list(hotel_res.data or [])
        if not flights or not hotels:
            repo.update_trip(
                session,
                trip_id,
                state=TripState.FAILED,
                flight_offers=flights,
                hotel_offers=hotels,
                error="No offers found for these dates.",
                error_code="no_offers",
                retryable=True,
            )
            raise AppError(
                404,
                "no_offers",
                "No offers",
                "No flights or hotels found for this search.",
                retryable=True,
            )

        within = filter_within_budget(flights, hotels, c.budget_usd)
        pairs: List[RankedPair] = []
        if within:
            for flight, hotel, cost in within[:20]:
                p = ProposedItinerary(flight=flight, hotel=hotel, total_usd=cost, within_budget=True)
                pairs.append(
                    RankedPair(
                        flight_offer_id=flight.offer_id,
                        hotel_offer_id=hotel.offer_id,
                        total_usd=cost,
                        within_budget=True,
                        score=score_itinerary(p),
                    )
                )
        else:
            # Still show all combinations marked over budget, cheapest first
            combos = []
            for flight in flights:
                for hotel in hotels:
                    cost = total_cost(flight, hotel)
                    combos.append((flight, hotel, cost))
            combos.sort(key=lambda x: x[2])
            for flight, hotel, cost in combos[:20]:
                p = ProposedItinerary(flight=flight, hotel=hotel, total_usd=cost, within_budget=False)
                pairs.append(
                    RankedPair(
                        flight_offer_id=flight.offer_id,
                        hotel_offer_id=hotel.offer_id,
                        total_usd=cost,
                        within_budget=False,
                        score=score_itinerary(p),
                    )
                )
        pairs.sort(key=lambda p: (-p.score, p.total_usd))

        weather = weather_res.data if weather_res.ok else None
        reviews = reviews_res.data if reviews_res.ok else None
        repo.update_trip(
            session,
            trip_id,
            state=TripState.COMPARE,
            flight_offers=flights,
            hotel_offers=hotels,
            ranked_pairs=pairs,
            weather=weather,
            reviews=reviews,
            clear_selection=True,
            clear_error=True,
            steps=row.steps + 1,
        )
        repo.add_audit(
            session,
            trip_id,
            "search_complete",
            {"flights": len(flights), "hotels": len(hotels), "pairs": len(pairs)},
        )
        log_event(logger, "search_complete", trip_id=trip_id, event="search_complete")
        return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]

    def select(
        self,
        session: Session,
        user: UserRow,
        trip_id: str,
        flight_offer_id: str,
        hotel_offer_id: str,
    ) -> TripResponse:
        row = self._owned(session, trip_id, user)
        if row.state not in {TripState.COMPARE.value, TripState.TRAVELERS.value, TripState.AWAIT_APPROVAL.value}:
            raise AppError(
                409,
                "invalid_state",
                "Invalid state",
                f"Cannot select offers while trip is in {row.state}.",
            )
        flights = [FlightOffer.model_validate(f) for f in __import__("json").loads(row.flight_offers_json)]
        hotels = [HotelOffer.model_validate(h) for h in __import__("json").loads(row.hotel_offers_json)]
        flight = next((f for f in flights if f.offer_id == flight_offer_id), None)
        hotel = next((h for h in hotels if h.offer_id == hotel_offer_id), None)
        if not flight or not hotel:
            raise AppError(404, "offer_not_found", "Offer not found", "Selected offer is not in search results.")

        c = TripConstraints.model_validate(__import__("json").loads(row.constraints_json))
        cost = total_cost(flight, hotel)
        within = c.budget_usd is None or cost <= c.budget_usd
        weather = (
            WeatherSummary.model_validate(__import__("json").loads(row.weather_json))
            if row.weather_json
            else None
        )
        reviews = (
            ReviewSummary.model_validate(__import__("json").loads(row.reviews_json))
            if row.reviews_json
            else None
        )
        proposal = ProposedItinerary(
            flight=flight,
            hotel=hotel,
            weather=weather,
            reviews=reviews,
            total_usd=cost,
            within_budget=within,
            summary=(
                f"{flight.carrier} {flight.origin}→{flight.destination}, "
                f"{hotel.name}, total ${cost:.2f}"
                + (" (within budget)" if within else " (OVER BUDGET)")
            ),
        )
        proposal = stamp_hash(validate_proposal_output(proposal))
        expires = datetime.utcnow() + timedelta(minutes=self.settings.proposal_ttl_minutes)
        proposal.expires_at = expires

        next_state = TripState.TRAVELERS
        if c.travelers and len(c.travelers) == c.adults:
            next_state = TripState.AWAIT_APPROVAL

        repo.update_trip(
            session,
            trip_id,
            state=next_state,
            selected_flight_id=flight_offer_id,
            selected_hotel_id=hotel_offer_id,
            proposal=proposal,
            proposal_expires_at=expires,
            clear_error=True,
        )
        repo.add_audit(
            session,
            trip_id,
            "offers_selected",
            {"flight_offer_id": flight_offer_id, "hotel_offer_id": hotel_offer_id},
        )
        return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]

    def update_travelers(
        self,
        session: Session,
        user: UserRow,
        trip_id: str,
        travelers: List[Traveler],
    ) -> TripResponse:
        row = self._owned(session, trip_id, user)
        if row.state not in {
            TripState.TRAVELERS.value,
            TripState.COMPARE.value,
            TripState.AWAIT_APPROVAL.value,
        }:
            raise AppError(
                409,
                "invalid_state",
                "Invalid state",
                f"Cannot update travelers while trip is in {row.state}.",
            )
        c = TripConstraints.model_validate(__import__("json").loads(row.constraints_json))
        if len(travelers) != c.adults:
            raise AppError(
                422,
                "traveler_count_mismatch",
                "Traveler count mismatch",
                f"Expected {c.adults} traveler(s), got {len(travelers)}.",
            )
        c.travelers = travelers
        next_state = TripState.AWAIT_APPROVAL if row.proposal_json else TripState.TRAVELERS
        repo.update_trip(session, trip_id, state=next_state, constraints=c, clear_error=True)
        repo.add_audit(session, trip_id, "travelers_updated", {"count": len(travelers)})
        return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]

    def approve(
        self,
        session: Session,
        user: UserRow,
        trip_id: str,
        proposal_id: str,
        itinerary_hash: str,
        acknowledge_over_budget: bool = False,
    ) -> TripResponse:
        row = self._owned(session, trip_id, user)
        current = repo.trip_to_response(row)
        if current.state == TripState.EXPIRED or (
            row.proposal_expires_at and row.proposal_expires_at < datetime.utcnow()
        ):
            repo.update_trip(
                session,
                trip_id,
                state=TripState.EXPIRED,
                error="Proposal expired.",
                error_code="proposal_expired",
                retryable=True,
            )
            raise AppError(
                409,
                "proposal_expired",
                "Proposal expired",
                "This proposal expired. Search again to continue.",
                retryable=True,
            )
        if current.state != TripState.AWAIT_APPROVAL:
            raise AppError(
                409,
                "invalid_state",
                "Invalid state",
                f"Trip is not awaiting approval (state={current.state}).",
            )
        if current.proposal is None:
            raise AppError(409, "missing_proposal", "Missing proposal", "No proposal to approve.")
        if len(current.constraints.travelers) != current.constraints.adults:
            raise AppError(
                422,
                "travelers_required",
                "Travelers required",
                "Complete traveler details before approving.",
            )
        if not current.proposal.within_budget and not acknowledge_over_budget:
            raise AppError(
                409,
                "over_budget_ack_required",
                "Over budget",
                "Itinerary exceeds budget. Set acknowledge_over_budget=true to proceed.",
            )

        ok, reason = validate_approval_for_booking(
            ApprovalRecord(
                trip_id=trip_id,
                proposal_id=proposal_id,
                itinerary_hash=itinerary_hash,
                approved_by=user.email,
                acknowledge_over_budget=acknowledge_over_budget,
            ),
            current.proposal,
            proposal_id=proposal_id,
            expected_hash=itinerary_hash,
        )
        if not ok:
            raise AppError(
                409,
                "approval_invalid",
                "Approval invalid",
                f"Approval rejected: {reason}",
            )

        approval = create_approval(trip_id, current.proposal, approved_by=user.email)
        approval.acknowledge_over_budget = acknowledge_over_budget
        repo.update_trip(session, trip_id, state=TripState.BOOK, approval=approval, clear_error=True)
        repo.add_audit(session, trip_id, "approval_granted", {"approval_id": approval.approval_id})

        proposal = current.proposal
        travelers = [
            {
                "id": str(i + 1),
                "dateOfBirth": (t.date_of_birth.isoformat() if t.date_of_birth else "1990-01-01"),
                "name": {"firstName": t.first_name, "lastName": t.last_name},
            }
            for i, t in enumerate(current.constraints.travelers)
        ]
        bookings: List[BookingRecord] = []

        if proposal.flight:
            import time

            repo.record_tool_call(
                session,
                trip_id,
                tool="book_flight",
                status="started",
                summary="Calling book_flight…",
                args={"offer_id": proposal.flight.offer_id, "approval_id": approval.approval_id},
            )
            t0 = time.perf_counter()
            flight_res = self.booking.book_flight(
                proposal.flight,
                travelers=travelers,
                approval_id=approval.approval_id,
                idempotency_key=f"{trip_id}-flight-{proposal.proposal_id}",
            )
            latency = round((time.perf_counter() - t0) * 1000, 2)
            if not flight_res.ok:
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool="book_flight",
                    status="error",
                    summary=flight_res.error.message if flight_res.error else "Flight booking failed",
                    args={"offer_id": proposal.flight.offer_id},
                    latency_ms=latency,
                )
                repo.update_trip(
                    session,
                    trip_id,
                    state=TripState.FAILED,
                    error=flight_res.error.message if flight_res.error else "Flight booking failed",
                    error_code=flight_res.error.code if flight_res.error else "flight_book_failed",
                    retryable=False,
                )
                raise AppError(
                    502,
                    flight_res.error.code if flight_res.error else "flight_book_failed",
                    "Flight booking failed",
                    flight_res.error.message if flight_res.error else "Flight booking failed",
                )
            repo.record_tool_call(
                session,
                trip_id,
                tool="book_flight",
                status="ok",
                summary=f"Booked flight ref {flight_res.data.provider_ref}",
                args={"offer_id": proposal.flight.offer_id},
                latency_ms=latency,
            )
            bookings.append(flight_res.data)

        if proposal.hotel:
            import time

            guests = [
                {
                    "tid": 1,
                    "title": "MR",
                    "firstName": travelers[0]["name"]["firstName"],
                    "lastName": travelers[0]["name"]["lastName"],
                    "phone": "+1234567890",
                    "email": current.constraints.travelers[0].email
                    or user.email,
                }
            ]
            repo.record_tool_call(
                session,
                trip_id,
                tool="book_hotel",
                status="started",
                summary="Calling book_hotel…",
                args={"offer_id": proposal.hotel.offer_id, "approval_id": approval.approval_id},
            )
            t0 = time.perf_counter()
            hotel_res = self.booking.book_hotel(
                proposal.hotel,
                guests=guests,
                approval_id=approval.approval_id,
                idempotency_key=f"{trip_id}-hotel-{proposal.proposal_id}",
            )
            latency = round((time.perf_counter() - t0) * 1000, 2)
            if not hotel_res.ok:
                repo.record_tool_call(
                    session,
                    trip_id,
                    tool="book_hotel",
                    status="error",
                    summary=hotel_res.error.message if hotel_res.error else "Hotel booking failed",
                    args={"offer_id": proposal.hotel.offer_id},
                    latency_ms=latency,
                )
                repo.update_trip(
                    session,
                    trip_id,
                    state=TripState.PARTIAL_FAILURE,
                    bookings=bookings,
                    error=hotel_res.error.message if hotel_res.error else "Hotel booking failed after flight",
                    error_code="partial_failure_hotel",
                    retryable=True,
                )
                repo.add_audit(session, trip_id, "partial_failure", {"bookings": len(bookings)})
                raise AppError(
                    502,
                    "partial_failure_hotel",
                    "Partial booking failure",
                    "Flight booked but hotel booking failed. Contact support or retry hotel.",
                    retryable=True,
                    extras={"bookings": [b.model_dump(mode="json") for b in bookings]},
                )
            repo.record_tool_call(
                session,
                trip_id,
                tool="book_hotel",
                status="ok",
                summary=f"Booked hotel ref {hotel_res.data.provider_ref}",
                args={"offer_id": proposal.hotel.offer_id},
                latency_ms=latency,
            )
            bookings.append(hotel_res.data)

        repo.update_trip(
            session,
            trip_id,
            state=TripState.CONFIRM,
            bookings=bookings,
            clear_error=True,
            clear_proposal_expiry=True,
        )
        repo.add_audit(
            session,
            trip_id,
            "booking_confirmed",
            {"refs": [b.provider_ref for b in bookings]},
        )
        log_event(logger, "booking_confirmed", trip_id=trip_id, event="booking_confirmed")
        return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]

    def reject(
        self,
        session: Session,
        user: UserRow,
        trip_id: str,
        feedback: Optional[str] = None,
        research: bool = True,
    ) -> TripResponse:
        self._owned(session, trip_id, user)
        repo.add_audit(session, trip_id, "proposal_rejected", {"feedback": feedback})
        if research:
            return self.search(session, user, trip_id)
        repo.update_trip(
            session,
            trip_id,
            state=TripState.COMPARE,
            clear_selection=True,
            clear_error=True,
        )
        return repo.trip_to_response(repo.get_trip(session, trip_id))  # type: ignore[arg-type]
