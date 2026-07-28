"""Trip and audit persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from travel_agent.db import AuditEventRow, TripRow
from travel_agent.models import (
    ApprovalRecord,
    BookingRecord,
    FlightOffer,
    HotelOffer,
    ProposedItinerary,
    RankedPair,
    ReviewSummary,
    ToolCallEvent,
    TripConstraints,
    TripResponse,
    TripState,
    TripSummary,
    WeatherSummary,
)


def _dumps(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(mode="json"))
    if isinstance(obj, list):
        return json.dumps(
            [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in obj]
        )
    return json.dumps(obj)


def _loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    return json.loads(raw)


def create_trip(
    session: Session,
    user_id: str,
    constraints: TripConstraints,
) -> TripRow:
    row = TripRow(
        user_id=user_id,
        state=TripState.INTAKE.value,
        constraints_json=_dumps(constraints),
    )
    session.add(row)
    session.flush()
    return row


def get_trip(session: Session, trip_id: str) -> Optional[TripRow]:
    return session.get(TripRow, trip_id)


def get_user_trip(session: Session, trip_id: str, user_id: str) -> Optional[TripRow]:
    row = get_trip(session, trip_id)
    if row is None or row.user_id != user_id:
        return None
    return row


def list_user_trips(session: Session, user_id: str) -> List[TripRow]:
    return (
        session.query(TripRow)
        .filter(TripRow.user_id == user_id)
        .order_by(TripRow.updated_at.desc())
        .all()
    )


def update_trip(
    session: Session,
    trip_id: str,
    *,
    state: Optional[TripState] = None,
    constraints: Optional[TripConstraints] = None,
    flight_offers: Optional[List[FlightOffer]] = None,
    hotel_offers: Optional[List[HotelOffer]] = None,
    ranked_pairs: Optional[List[RankedPair]] = None,
    selected_flight_id: Optional[str] = None,
    selected_hotel_id: Optional[str] = None,
    clear_selection: bool = False,
    weather: Optional[WeatherSummary] = None,
    reviews: Optional[ReviewSummary] = None,
    proposal: Optional[ProposedItinerary] = None,
    proposal_expires_at: Optional[datetime] = None,
    clear_proposal_expiry: bool = False,
    bookings: Optional[List[BookingRecord]] = None,
    approval: Optional[ApprovalRecord] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
    retryable: Optional[bool] = None,
    clear_error: bool = False,
    cost_usd: Optional[float] = None,
    steps: Optional[int] = None,
) -> TripRow:
    row = get_trip(session, trip_id)
    if row is None:
        raise KeyError(f"trip not found: {trip_id}")
    if state is not None:
        row.state = state.value
    if constraints is not None:
        row.constraints_json = _dumps(constraints)
    if flight_offers is not None:
        row.flight_offers_json = _dumps(flight_offers)
    if hotel_offers is not None:
        row.hotel_offers_json = _dumps(hotel_offers)
    if ranked_pairs is not None:
        row.ranked_pairs_json = _dumps(ranked_pairs)
    if clear_selection:
        row.selected_flight_id = None
        row.selected_hotel_id = None
    else:
        if selected_flight_id is not None:
            row.selected_flight_id = selected_flight_id
        if selected_hotel_id is not None:
            row.selected_hotel_id = selected_hotel_id
    if weather is not None:
        row.weather_json = _dumps(weather)
    if reviews is not None:
        row.reviews_json = _dumps(reviews)
    if proposal is not None:
        row.proposal_json = _dumps(proposal)
    if clear_proposal_expiry:
        row.proposal_expires_at = None
    elif proposal_expires_at is not None:
        row.proposal_expires_at = proposal_expires_at
    if bookings is not None:
        row.bookings_json = _dumps(bookings)
    if approval is not None:
        row.approval_json = _dumps(approval)
    if clear_error:
        row.error = None
        row.error_code = None
        row.retryable = False
    else:
        if error is not None:
            row.error = error
        if error_code is not None:
            row.error_code = error_code
        if retryable is not None:
            row.retryable = retryable
    if cost_usd is not None:
        row.cost_usd = cost_usd
    if steps is not None:
        row.steps = steps
    session.flush()
    return row


def trip_to_response(row: TripRow, session: Optional[Session] = None) -> TripResponse:
    from sqlalchemy.orm import object_session

    proposal_raw = _loads(row.proposal_json, None)
    approval_raw = _loads(row.approval_json, None)
    bookings_raw = _loads(row.bookings_json, [])
    weather_raw = _loads(row.weather_json, None)
    reviews_raw = _loads(row.reviews_json, None)
    sess = session or object_session(row)
    tool_calls: List[ToolCallEvent] = []
    if sess is not None:
        tool_calls = list_tool_calls(sess, row.id)
    weather = WeatherSummary.model_validate(weather_raw) if weather_raw else None
    daily_weather = list(weather.daily) if weather and weather.daily else []
    return TripResponse(
        trip_id=UUID(row.id),
        user_id=row.user_id,
        state=TripState(row.state),
        constraints=TripConstraints.model_validate(_loads(row.constraints_json, {})),
        flight_offers=[
            FlightOffer.model_validate(f) for f in _loads(row.flight_offers_json, [])
        ],
        hotel_offers=[HotelOffer.model_validate(h) for h in _loads(row.hotel_offers_json, [])],
        ranked_pairs=[RankedPair.model_validate(p) for p in _loads(row.ranked_pairs_json, [])],
        selected_flight_id=row.selected_flight_id,
        selected_hotel_id=row.selected_hotel_id,
        proposal=ProposedItinerary.model_validate(proposal_raw) if proposal_raw else None,
        weather=weather,
        daily_weather=daily_weather,
        reviews=ReviewSummary.model_validate(reviews_raw) if reviews_raw else None,
        bookings=[BookingRecord.model_validate(b) for b in bookings_raw],
        approval=ApprovalRecord.model_validate(approval_raw) if approval_raw else None,
        tool_calls=tool_calls,
        error=row.error,
        error_code=row.error_code,
        retryable=bool(row.retryable),
        cost_usd=row.cost_usd,
        steps=row.steps,
        proposal_expires_at=row.proposal_expires_at,
    )


def trip_to_summary(row: TripRow) -> TripSummary:
    constraints = TripConstraints.model_validate(_loads(row.constraints_json, {}))
    proposal_raw = _loads(row.proposal_json, None)
    total = None
    if proposal_raw:
        total = proposal_raw.get("total_usd")
    return TripSummary(
        trip_id=UUID(row.id),
        state=TripState(row.state),
        origin=constraints.origin,
        destination=constraints.destination,
        departure_date=constraints.departure_date,
        return_date=constraints.return_date,
        total_usd=total,
        updated_at=row.updated_at,
    )


def add_audit(
    session: Session,
    trip_id: str,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditEventRow:
    event = AuditEventRow(
        trip_id=trip_id,
        event_type=event_type,
        payload_json=_dumps(payload or {}),
    )
    session.add(event)
    session.flush()
    return event


def record_tool_call(
    session: Session,
    trip_id: str,
    *,
    tool: str,
    status: str,
    summary: str = "",
    args: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[float] = None,
) -> AuditEventRow:
    return add_audit(
        session,
        trip_id,
        "tool_call",
        {
            "tool": tool,
            "status": status,
            "summary": summary,
            "args": args or {},
            "latency_ms": latency_ms,
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
    )


def list_tool_calls(session: Session, trip_id: str) -> List[ToolCallEvent]:
    rows = (
        session.query(AuditEventRow)
        .filter(AuditEventRow.trip_id == trip_id, AuditEventRow.event_type == "tool_call")
        .order_by(AuditEventRow.created_at.asc())
        .all()
    )
    out: List[ToolCallEvent] = []
    for row in rows:
        payload = _loads(row.payload_json, {})
        out.append(
            ToolCallEvent(
                tool=str(payload.get("tool", "unknown")),
                status=str(payload.get("status", "ok")),
                summary=str(payload.get("summary", "")),
                args=payload.get("args") or {},
                latency_ms=payload.get("latency_ms"),
                created_at=row.created_at,
            )
        )
    return out
