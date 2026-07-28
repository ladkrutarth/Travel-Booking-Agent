"""Input/output safety guardrails."""

from __future__ import annotations

import re
from typing import Tuple

from travel_agent.models import ProposedItinerary

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(earlier|previous|prior)\s+(rules|instructions)", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"do\s+not\s+follow\s+safety", re.I),
]

_BOOK_WITHOUT_APPROVAL = re.compile(
    r"(book|charge|purchase).{0,60}(without|skip|no\s+human).{0,30}(approv|confirm)",
    re.I,
)

_OFF_DOMAIN = re.compile(
    r"\b(write malware|hack into|exploit|build a bomb)\b",
    re.I,
)

_SECRET_LEAK = re.compile(
    r"(api[_-]?key|secret|password|bearer\s+[a-z0-9\.\-_]+)",
    re.I,
)


class OutputValidationError(ValueError):
    pass


def sanitize_user_text(text: str, max_len: int = 4000) -> str:
    cleaned = text.replace("\x00", "").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def validate_input(text: str) -> Tuple[bool, str]:
    """Return (allowed, reason). Fail closed on risky inputs."""
    if not text or not text.strip():
        return False, "empty_input"
    lowered_check = text.strip()
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(lowered_check):
            return False, "prompt_injection"
    if _OFF_DOMAIN.search(lowered_check):
        return False, "off_domain"
    if _BOOK_WITHOUT_APPROVAL.search(lowered_check):
        return False, "unapproved_booking_attempt"
    return True, "ok"


def validate_proposal_output(proposal: ProposedItinerary) -> ProposedItinerary:
    if proposal.total_usd < 0:
        raise OutputValidationError("negative_total")
    if proposal.flight and proposal.hotel:
        expected = proposal.flight.price_usd + proposal.hotel.price_usd
        if abs(proposal.total_usd - expected) > 0.05:
            proposal.total_usd = round(expected, 2)
    summary = proposal.summary or ""
    if _SECRET_LEAK.search(summary):
        raise OutputValidationError("secret_leak_in_summary")
    proposal.summary = summary[:2000]
    return proposal
