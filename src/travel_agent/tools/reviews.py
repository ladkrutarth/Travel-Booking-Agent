"""Google Places reviews tool (advisory only)."""

from __future__ import annotations

from typing import Optional

import httpx

from travel_agent.config import Settings, get_settings
from travel_agent.models import ReviewSummary, ToolError, ToolResult
from travel_agent.observability.logging import get_logger

logger = get_logger(__name__)


class ReviewsClient:
    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.Client] = None):
        self.settings = settings or get_settings()
        self._client = client or httpx.Client(timeout=15.0)

    def close(self) -> None:
        self._client.close()

    def get_reviews(self, place_name: str, location: Optional[str] = None) -> ToolResult:
        try:
            query = f"{place_name} {location}".strip() if location else place_name
            if self.settings.google_places_mock or not self.settings.google_places_api_key:
                return ToolResult(
                    ok=True,
                    data=ReviewSummary(
                        place_name=place_name,
                        rating=4.4,
                        review_count=128,
                        snippets=[
                            "Clean rooms and friendly staff.",
                            "Great location for walking the city.",
                        ],
                    ),
                )
            find = self._client.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={
                    "input": query,
                    "inputtype": "textquery",
                    "fields": "place_id,name",
                    "key": self.settings.google_places_api_key,
                },
            )
            if find.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(code="places_find_failed", message=find.text, retryable=True),
                )
            candidates = find.json().get("candidates") or []
            if not candidates:
                return ToolResult(
                    ok=True,
                    data=ReviewSummary(
                        place_name=place_name, rating=0.0, review_count=0, snippets=[]
                    ),
                )
            place_id = candidates[0]["place_id"]
            details = self._client.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": place_id,
                    "fields": "name,rating,user_ratings_total,reviews",
                    "key": self.settings.google_places_api_key,
                },
            )
            if details.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="places_details_failed", message=details.text, retryable=True
                    ),
                )
            result = details.json().get("result", {})
            snippets = [r.get("text", "")[:180] for r in (result.get("reviews") or [])[:3]]
            return ToolResult(
                ok=True,
                data=ReviewSummary(
                    place_name=result.get("name", place_name),
                    rating=float(result.get("rating") or 0),
                    review_count=int(result.get("user_ratings_total") or 0),
                    snippets=snippets,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_reviews failed")
            return ToolResult(
                ok=False,
                error=ToolError(code="reviews_exception", message=str(exc), retryable=True),
            )
