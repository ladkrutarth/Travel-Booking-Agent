"""Approval token and itinerary hash gate for booking side effects."""

from __future__ import annotations

import hashlib
import json
from typing import Optional, Tuple

from travel_agent.models import ApprovalRecord, ProposedItinerary


def itinerary_hash(proposal: ProposedItinerary) -> str:
    payload = {
        "flight_id": proposal.flight.offer_id if proposal.flight else None,
        "flight_price": proposal.flight.price_usd if proposal.flight else None,
        "hotel_id": proposal.hotel.offer_id if proposal.hotel else None,
        "hotel_price": proposal.hotel.price_usd if proposal.hotel else None,
        "total_usd": proposal.total_usd,
        "version": proposal.version,
        "proposal_id": proposal.proposal_id,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stamp_hash(proposal: ProposedItinerary) -> ProposedItinerary:
    proposal.itinerary_hash = itinerary_hash(proposal)
    return proposal


def create_approval(
    trip_id: str,
    proposal: ProposedItinerary,
    *,
    approved_by: str = "user",
) -> ApprovalRecord:
    return ApprovalRecord(
        trip_id=trip_id,
        proposal_id=proposal.proposal_id,
        itinerary_hash=proposal.itinerary_hash or itinerary_hash(proposal),
        approved_by=approved_by,
    )


def validate_approval_for_booking(
    approval: Optional[ApprovalRecord],
    proposal: Optional[ProposedItinerary],
    *,
    proposal_id: Optional[str] = None,
    expected_hash: Optional[str] = None,
) -> Tuple[bool, str]:
    if approval is None:
        return False, "missing_approval"
    if proposal is None:
        return False, "missing_proposal"
    if proposal_id and approval.proposal_id != proposal_id:
        return False, "proposal_id_mismatch"
    if proposal_id and proposal.proposal_id != proposal_id:
        return False, "proposal_id_mismatch"
    current_hash = proposal.itinerary_hash or itinerary_hash(proposal)
    if approval.itinerary_hash != current_hash:
        return False, "itinerary_hash_mismatch"
    if expected_hash and expected_hash != current_hash:
        return False, "submitted_hash_mismatch"
    return True, "ok"
