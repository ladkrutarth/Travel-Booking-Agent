"""LangGraph travel booking state machine."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from travel_agent.config import Settings, get_settings
from travel_agent.models import (
    BookingRecord,
    FlightOffer,
    HotelOffer,
    ProposedItinerary,
    ReviewSummary,
    Traveler,
    TripConstraints,
    TripState,
    WeatherSummary,
)
from travel_agent.observability import CostTracker, timed_span
from travel_agent.observability.logging import get_logger, log_event
from travel_agent.policies.approval import stamp_hash, validate_approval_for_booking
from travel_agent.policies.budget import filter_within_budget, score_itinerary, total_cost
from travel_agent.policies.safety import sanitize_user_text, validate_proposal_output
from travel_agent.tools.amadeus import AmadeusClient
from travel_agent.tools.reviews import ReviewsClient
from travel_agent.tools.weather import WeatherClient

logger = get_logger(__name__)

_IATA = {
    "new york": "JFK",
    "nyc": "JFK",
    "los angeles": "LAX",
    "san francisco": "SFO",
    "chicago": "ORD",
    "miami": "MIA",
    "seattle": "SEA",
    "boston": "BOS",
    "london": "LHR",
    "paris": "CDG",
    "tokyo": "NRT",
    "rome": "FCO",
    "barcelona": "BCN",
    "madrid": "MAD",
    "amsterdam": "AMS",
    "dubai": "DXB",
}


class AgentState(TypedDict, total=False):
    trip_id: str
    state: str
    messages: List[Dict[str, str]]
    constraints: Dict[str, Any]
    flight_offers: List[Dict[str, Any]]
    hotel_offers: List[Dict[str, Any]]
    weather: Optional[Dict[str, Any]]
    reviews: Optional[Dict[str, Any]]
    proposal: Optional[Dict[str, Any]]
    approval: Optional[Dict[str, Any]]
    bookings: List[Dict[str, Any]]
    error: Optional[str]
    cost_usd: float
    steps: int
    user_message: str
    reject_feedback: Optional[str]
    approved: bool


def _city_to_iata(text: str) -> Optional[str]:
    t = text.lower().strip()
    if re.fullmatch(r"[A-Za-z]{3}", t):
        return t.upper()
    for name, code in _IATA.items():
        if name in t:
            return code
    return None


def _parse_date(text: str) -> Optional[date]:
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def extract_constraints_heuristic(message: str, existing: TripConstraints) -> TripConstraints:
    """Deterministic constraint extraction when no LLM key is available."""
    data = existing.model_dump()
    msg = message.lower()

    budget = re.search(r"\$\s?(\d+(?:\.\d+)?)|\bbudget(?:\s+of)?\s+(\d+(?:\.\d+)?)", msg)
    if budget:
        data["budget_usd"] = float(budget.group(1) or budget.group(2))
    under = re.search(r"under\s+\$?\s?(\d+(?:\.\d+)?)", msg)
    if under and not data.get("budget_usd"):
        data["budget_usd"] = float(under.group(1))

    adults = re.search(r"(\d+)\s+adults?", msg)
    if adults:
        data["adults"] = int(adults.group(1))

    # "from X to Y"
    route = re.search(r"from\s+([a-zA-Z\s]{3,30}?)\s+to\s+([a-zA-Z\s]{3,30})", message, re.I)
    if route:
        origin = _city_to_iata(route.group(1))
        dest = _city_to_iata(route.group(2))
        if origin:
            data["origin"] = origin
        if dest:
            data["destination"] = dest
            data["destination_city"] = route.group(2).strip().title()

    if not data.get("destination"):
        for name, code in _IATA.items():
            if re.search(rf"\bto\s+{re.escape(name)}\b", msg) or re.search(
                rf"\b(?:in|visit|trip to)\s+{re.escape(name)}\b", msg
            ):
                data["destination"] = code
                data["destination_city"] = name.title()
                break

    if not data.get("origin"):
        for name, code in _IATA.items():
            if re.search(rf"\bfrom\s+{re.escape(name)}\b", msg):
                data["origin"] = code
                break

    dep = _parse_date(message)
    if dep:
        data["departure_date"] = dep
    ret = None
    dates = re.findall(r"20\d{2}-\d{2}-\d{2}", message)
    if len(dates) >= 2:
        data["departure_date"] = date.fromisoformat(dates[0])
        data["return_date"] = date.fromisoformat(dates[1])
    elif dep and not data.get("return_date"):
        data["return_date"] = dep + timedelta(days=3)

    # Defaults for demo completeness when partial
    if not data.get("origin"):
        data["origin"] = "JFK"
    if not data.get("destination"):
        data["destination"] = "LAX"
        data["destination_city"] = data.get("destination_city") or "Los Angeles"
    if not data.get("departure_date"):
        data["departure_date"] = date.today() + timedelta(days=21)
    if not data.get("return_date"):
        data["return_date"] = data["departure_date"] + timedelta(days=4)
    if not data.get("travelers"):
        data["travelers"] = [
            Traveler(first_name="Alex", last_name="Traveler", email="alex@example.com").model_dump(
                mode="json"
            )
        ]

    return TripConstraints.model_validate(data)


def _constraints_complete(c: TripConstraints) -> bool:
    return bool(c.origin and c.destination and c.departure_date and c.return_date)


class TravelBookingGraph:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        amadeus: Optional[AmadeusClient] = None,
        weather: Optional[WeatherClient] = None,
        reviews: Optional[ReviewsClient] = None,
    ):
        self.settings = settings or get_settings()
        self.amadeus = amadeus or AmadeusClient(self.settings)
        self.weather = weather or WeatherClient(self.settings)
        self.reviews = reviews or ReviewsClient(self.settings)
        self.graph = self._build()

    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("intake", self.intake)
        g.add_node("constraints", self.constraints_node)
        g.add_node("search", self.search)
        g.add_node("rank", self.rank)
        g.add_node("propose", self.propose)
        g.add_node("await_approval", self.await_approval)
        g.add_node("book", self.book)
        g.add_node("confirm", self.confirm)
        g.add_node("failed", self.failed)

        g.set_entry_point("intake")
        g.add_edge("intake", "constraints")
        g.add_conditional_edges(
            "constraints",
            self._after_constraints,
            {"search": "search", "propose": "propose", "failed": "failed"},
        )
        g.add_conditional_edges(
            "search",
            self._after_search,
            {"rank": "rank", "failed": "failed"},
        )
        g.add_edge("rank", "propose")
        g.add_edge("propose", "await_approval")
        g.add_conditional_edges(
            "await_approval",
            self._after_approval,
            {"book": "book", "search": "search", "end": END},
        )
        g.add_conditional_edges(
            "book",
            self._after_book,
            {"confirm": "confirm", "failed": "failed"},
        )
        g.add_edge("confirm", END)
        g.add_edge("failed", END)
        return g.compile()

    def _tracker(self, state: AgentState) -> CostTracker:
        return CostTracker(
            trip_id=state.get("trip_id", ""),
            max_cost_usd=self.settings.max_trip_cost_usd,
            spent_usd=float(state.get("cost_usd") or 0.0),
            steps=int(state.get("steps") or 0),
            max_steps=self.settings.max_agent_steps,
        )

    def _bump(self, state: AgentState, tracker: CostTracker) -> Dict[str, Any]:
        tracker.bump_step()
        tracker.assert_within_limits()
        return {"steps": tracker.steps, "cost_usd": tracker.spent_usd}

    def intake(self, state: AgentState) -> Dict[str, Any]:
        if self.settings.kill_switch:
            return {
                "state": TripState.FAILED.value,
                "error": "kill_switch_enabled",
            }
        tracker = self._tracker(state)
        with timed_span("intake", trip_id=state.get("trip_id")):
            msg = sanitize_user_text(state.get("user_message") or "")
            messages = list(state.get("messages") or [])
            if msg:
                messages.append({"role": "user", "content": msg})
            updates = self._bump(state, tracker)
            updates.update(
                {
                    "state": TripState.INTAKE.value,
                    "messages": messages,
                    "user_message": msg,
                    "error": None,
                }
            )
            return updates

    def constraints_node(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        with timed_span("constraints", trip_id=state.get("trip_id")):
            existing = TripConstraints.model_validate(state.get("constraints") or {})
            msg = state.get("user_message") or ""
            # Optional LLM extraction path (falls back to heuristic)
            constraints = self._extract_with_llm_or_heuristic(msg, existing)
            updates = self._bump(state, tracker)
            updates.update(
                {
                    "state": TripState.CONSTRAINTS.value,
                    "constraints": constraints.model_dump(mode="json"),
                }
            )
            if not _constraints_complete(constraints):
                updates["error"] = "incomplete_constraints"
            return updates

    def _extract_with_llm_or_heuristic(
        self, message: str, existing: TripConstraints
    ) -> TripConstraints:
        if not self.settings.openai_api_key or not message:
            return extract_constraints_heuristic(message or "", existing)
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = ChatOpenAI(
                model=self.settings.llm_extraction_model,
                api_key=self.settings.openai_api_key,
                temperature=0,
            )
            prompt = (
                "Extract travel constraints as JSON with keys: origin, destination, "
                "destination_city, departure_date, return_date, adults, budget_usd, preferences. "
                "Use IATA codes for airports. Dates as YYYY-MM-DD. Omit unknown fields."
            )
            resp = llm.invoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=message),
                ]
            )
            content = str(resp.content)
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                parsed = json.loads(m.group(0))
                merged = existing.model_dump()
                merged.update({k: v for k, v in parsed.items() if v is not None})
                return extract_constraints_heuristic(message, TripConstraints.model_validate(merged))
        except Exception:  # noqa: BLE001
            logger.exception("LLM constraint extraction failed; using heuristic")
        return extract_constraints_heuristic(message, existing)

    def search(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        with timed_span("search", trip_id=state.get("trip_id")):
            c = TripConstraints.model_validate(state.get("constraints") or {})
            assert c.origin and c.destination and c.departure_date

            flight_res = self.amadeus.search_flights(
                origin=c.origin,
                destination=c.destination,
                departure_date=c.departure_date,
                adults=c.adults,
                return_date=c.return_date,
            )
            hotel_city = c.destination  # IATA city/airport code works for mock; Amadeus wants city
            hotel_res = self.amadeus.search_hotels(
                city_code=hotel_city,
                check_in=c.departure_date,
                check_out=c.return_date,
                adults=c.adults,
            )
            weather_res = self.weather.get_weather(c.destination_city or c.destination)
            reviews_res = self.reviews.get_reviews(
                place_name=c.destination_city or c.destination,
                location=c.destination_city,
            )

            updates = self._bump(state, tracker)
            tracker.add_flat(0.01)  # tool call accounting stub
            updates["cost_usd"] = tracker.spent_usd

            if not flight_res.ok:
                updates.update(
                    {
                        "state": TripState.FAILED.value,
                        "error": flight_res.error.message if flight_res.error else "flight_search",
                    }
                )
                return updates
            if not hotel_res.ok:
                updates.update(
                    {
                        "state": TripState.FAILED.value,
                        "error": hotel_res.error.message if hotel_res.error else "hotel_search",
                    }
                )
                return updates

            flights = [f.model_dump(mode="json") for f in flight_res.data]
            hotels = [h.model_dump(mode="json") for h in hotel_res.data]
            updates.update(
                {
                    "state": TripState.SEARCH.value,
                    "flight_offers": flights,
                    "hotel_offers": hotels,
                    "weather": weather_res.data.model_dump(mode="json")
                    if weather_res.ok and weather_res.data
                    else None,
                    "reviews": reviews_res.data.model_dump(mode="json")
                    if reviews_res.ok and reviews_res.data
                    else None,
                    "error": None,
                }
            )
            log_event(
                logger,
                "search_complete",
                trip_id=state.get("trip_id"),
                event="search_complete",
                tool="amadeus",
            )
            return updates

    def rank(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        with timed_span("rank", trip_id=state.get("trip_id")):
            c = TripConstraints.model_validate(state.get("constraints") or {})
            flights = [FlightOffer.model_validate(f) for f in state.get("flight_offers") or []]
            hotels = [HotelOffer.model_validate(h) for h in state.get("hotel_offers") or []]
            pairs = filter_within_budget(flights, hotels, c.budget_usd)
            updates = self._bump(state, tracker)
            if not pairs:
                # Degrade: pick cheapest overall and mark over budget
                if flights and hotels:
                    flight = min(flights, key=lambda x: x.price_usd)
                    hotel = min(hotels, key=lambda x: x.price_usd)
                    cost = total_cost(flight, hotel)
                    proposal = ProposedItinerary(
                        flight=flight,
                        hotel=hotel,
                        weather=WeatherSummary.model_validate(state["weather"])
                        if state.get("weather")
                        else None,
                        reviews=ReviewSummary.model_validate(state["reviews"])
                        if state.get("reviews")
                        else None,
                        total_usd=cost,
                        within_budget=False,
                        summary=(
                            f"No options within budget ${c.budget_usd}. "
                            f"Cheapest available total ${cost:.2f}."
                        ),
                    )
                    proposal = stamp_hash(validate_proposal_output(proposal))
                    updates.update(
                        {
                            "state": TripState.RANK.value,
                            "proposal": proposal.model_dump(mode="json"),
                        }
                    )
                    return updates
                updates.update({"state": TripState.FAILED.value, "error": "no_offers"})
                return updates

            # Score top candidates
            candidates: List[ProposedItinerary] = []
            for flight, hotel, cost in pairs[:10]:
                p = ProposedItinerary(
                    flight=flight,
                    hotel=hotel,
                    weather=WeatherSummary.model_validate(state["weather"])
                    if state.get("weather")
                    else None,
                    reviews=ReviewSummary.model_validate(state["reviews"])
                    if state.get("reviews")
                    else None,
                    total_usd=cost,
                    within_budget=True,
                    summary="",
                )
                candidates.append(p)
            best = max(candidates, key=lambda p: score_itinerary(p))
            updates.update(
                {
                    "state": TripState.RANK.value,
                    "proposal": best.model_dump(mode="json"),
                }
            )
            return updates

    def propose(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        with timed_span("propose", trip_id=state.get("trip_id")):
            proposal = ProposedItinerary.model_validate(state.get("proposal") or {})
            c = TripConstraints.model_validate(state.get("constraints") or {})
            if not proposal.summary:
                flight = proposal.flight
                hotel = proposal.hotel
                proposal.summary = (
                    f"Propose {flight.carrier if flight else '?'} {flight.origin if flight else ''}→"
                    f"{flight.destination if flight else ''} on {c.departure_date}, "
                    f"stay at {hotel.name if hotel else 'hotel'}, "
                    f"total ${proposal.total_usd:.2f}"
                    + (" (within budget)." if proposal.within_budget else " (OVER BUDGET).")
                )
            proposal = stamp_hash(validate_proposal_output(proposal))
            messages = list(state.get("messages") or [])
            messages.append({"role": "assistant", "content": proposal.summary})
            updates = self._bump(state, tracker)
            updates.update(
                {
                    "state": TripState.PROPOSE.value,
                    "proposal": proposal.model_dump(mode="json"),
                    "messages": messages,
                    "approved": False,
                }
            )
            return updates

    def await_approval(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        updates = self._bump(state, tracker)
        # HITL: graph pauses here at API layer; when resumed, `approved` or reject_feedback is set
        updates["state"] = TripState.AWAIT_APPROVAL.value
        return updates

    def book(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        with timed_span("book", trip_id=state.get("trip_id")):
            from travel_agent.models import ApprovalRecord

            proposal = ProposedItinerary.model_validate(state.get("proposal") or {})
            approval = (
                ApprovalRecord.model_validate(state["approval"]) if state.get("approval") else None
            )
            ok, reason = validate_approval_for_booking(approval, proposal)
            if not ok:
                return {
                    **self._bump(state, tracker),
                    "state": TripState.FAILED.value,
                    "error": f"booking_blocked:{reason}",
                }

            assert approval is not None
            c = TripConstraints.model_validate(state.get("constraints") or {})
            travelers = [
                {
                    "id": "1",
                    "dateOfBirth": (t.date_of_birth.isoformat() if t.date_of_birth else "1990-01-01"),
                    "name": {
                        "firstName": t.first_name,
                        "lastName": t.last_name,
                    },
                }
                for t in (c.travelers or [Traveler(first_name="Alex", last_name="Traveler")])
            ]

            bookings: List[BookingRecord] = []
            if proposal.flight:
                flight_res = self.amadeus.book_flight(
                    proposal.flight,
                    travelers=travelers,
                    approval_id=approval.approval_id,
                    idempotency_key=f"{state['trip_id']}-flight-{proposal.proposal_id}",
                )
                if not flight_res.ok:
                    return {
                        **self._bump(state, tracker),
                        "state": TripState.FAILED.value,
                        "error": flight_res.error.message if flight_res.error else "flight_book",
                    }
                bookings.append(flight_res.data)

            if proposal.hotel:
                guests = [
                    {
                        "tid": 1,
                        "title": "MR",
                        "firstName": travelers[0]["name"]["firstName"],
                        "lastName": travelers[0]["name"]["lastName"],
                        "phone": "+1234567890",
                        "email": "alex@example.com",
                    }
                ]
                hotel_res = self.amadeus.book_hotel(
                    proposal.hotel,
                    guests=guests,
                    approval_id=approval.approval_id,
                    idempotency_key=f"{state['trip_id']}-hotel-{proposal.proposal_id}",
                )
                if not hotel_res.ok:
                    return {
                        **self._bump(state, tracker),
                        "state": TripState.FAILED.value,
                        "error": hotel_res.error.message if hotel_res.error else "hotel_book",
                        "bookings": [b.model_dump(mode="json") for b in bookings],
                    }
                bookings.append(hotel_res.data)

            updates = self._bump(state, tracker)
            updates.update(
                {
                    "state": TripState.BOOK.value,
                    "bookings": [b.model_dump(mode="json") for b in bookings],
                    "error": None,
                }
            )
            return updates

    def confirm(self, state: AgentState) -> Dict[str, Any]:
        tracker = self._tracker(state)
        messages = list(state.get("messages") or [])
        refs = ", ".join(
            b.get("provider_ref", "") for b in (state.get("bookings") or []) if b.get("provider_ref")
        )
        messages.append(
            {
                "role": "assistant",
                "content": f"Booking confirmed. References: {refs or 'n/a'}",
            }
        )
        updates = self._bump(state, tracker)
        updates.update({"state": TripState.CONFIRM.value, "messages": messages})
        return updates

    def failed(self, state: AgentState) -> Dict[str, Any]:
        return {"state": TripState.FAILED.value}

    def _after_constraints(self, state: AgentState) -> str:
        if state.get("error") == "incomplete_constraints":
            # Still proceed with defaults filled by heuristic; only fail if kill/error other
            pass
        if state.get("state") == TripState.FAILED.value:
            return "failed"
        if state.get("approved"):
            return "search"
        return "search"

    def _after_search(self, state: AgentState) -> str:
        if state.get("state") == TripState.FAILED.value or state.get("error"):
            return "failed"
        return "rank"

    def _after_approval(self, state: AgentState) -> str:
        if state.get("approved") and state.get("approval"):
            return "book"
        if state.get("reject_feedback") is not None:
            return "search"
        return "end"

    def _after_book(self, state: AgentState) -> str:
        if state.get("state") == TripState.FAILED.value or state.get("error"):
            return "failed"
        return "confirm"

    def run_to_proposal(self, initial: AgentState) -> AgentState:
        result = self.graph.invoke(initial)
        return result  # type: ignore[return-value]

    def execute_booking(self, state: AgentState) -> AgentState:
        """Run BOOK → CONFIRM only. Requires approval already attached on state."""
        current: AgentState = dict(state)  # type: ignore[assignment]
        current["approved"] = True
        book_updates = self.book(current)
        current.update(book_updates)  # type: ignore[arg-type]
        if current.get("state") == TripState.FAILED.value or current.get("error"):
            fail_updates = self.failed(current)
            current.update(fail_updates)  # type: ignore[arg-type]
            return current
        confirm_updates = self.confirm(current)
        current.update(confirm_updates)  # type: ignore[arg-type]
        return current

    def replan_after_reject(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """Re-run SEARCH → RANK → PROPOSE after rejection."""
        current: AgentState = dict(state)  # type: ignore[assignment]
        current["approved"] = False
        current["approval"] = None
        current["reject_feedback"] = feedback or ""
        if feedback:
            messages = list(current.get("messages") or [])
            messages.append({"role": "user", "content": f"Reject feedback: {feedback}"})
            current["messages"] = messages
            current["user_message"] = feedback
            # Merge feedback into constraints (e.g. lower budget / prefs)
            c = TripConstraints.model_validate(current.get("constraints") or {})
            c = extract_constraints_heuristic(feedback, c)
            current["constraints"] = c.model_dump(mode="json")
        for node in (self.search, self.rank, self.propose, self.await_approval):
            updates = node(current)
            current.update(updates)  # type: ignore[arg-type]
            if current.get("state") == TripState.FAILED.value:
                break
        return current


def new_trip_state(
    trip_id: str,
    message: str,
    constraints: Optional[TripConstraints] = None,
) -> AgentState:
    return {
        "trip_id": trip_id,
        "state": TripState.INTAKE.value,
        "messages": [],
        "constraints": (constraints or TripConstraints()).model_dump(mode="json"),
        "flight_offers": [],
        "hotel_offers": [],
        "weather": None,
        "reviews": None,
        "proposal": None,
        "approval": None,
        "bookings": [],
        "error": None,
        "cost_usd": 0.0,
        "steps": 0,
        "user_message": message,
        "reject_feedback": None,
        "approved": False,
    }
