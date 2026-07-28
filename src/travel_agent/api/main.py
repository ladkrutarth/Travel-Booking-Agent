"""FastAPI application — JSON API only (Next.js owns UI)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from travel_agent.api.deps import current_user, db_session
from travel_agent.auth import (
    create_access_token,
    create_refresh_token,
    create_user,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    user_to_response,
    verify_password,
)
from travel_agent.data.airports import AirportSearchResult, search_airports
from travel_agent.config import get_settings
from travel_agent.db import UserRow, init_db
from travel_agent.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
)
from travel_agent.models import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    TravelersUpdateRequest,
    TripApproveRequest,
    TripCreateRequest,
    TripRejectRequest,
    TripResponse,
    TripSelectRequest,
    TripSummary,
    UserResponse,
)
from travel_agent.observability import configure_tracing
from travel_agent.observability.logging import configure_logging, get_logger
from travel_agent.service import TripService

configure_logging()
configure_tracing()
logger = get_logger(__name__)

_service: Optional[TripService] = None


def get_service() -> TripService:
    global _service
    if _service is None:
        _service = TripService()
    return _service


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db()
        logger.info("api_started env=%s", get_settings().app_env)
        yield

    application = FastAPI(
        title="Travel Booking Agent API",
        version="0.2.0",
        description="Production booking API with auth, HITL approval, and edge-case handling.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)

    @application.get("/health")
    def health() -> dict:
        s = get_settings()
        return {
            "status": "degraded" if s.kill_switch else "ok",
            "kill_switch": s.kill_switch,
            "flight_sources": s.flight_sources,
        }

    @application.get("/airports/search", response_model=List[AirportSearchResult])
    def airports_search(q: str = "", limit: int = 12) -> List[AirportSearchResult]:
        return search_airports(q, limit=min(max(limit, 1), 25))

    @application.post("/auth/signup", response_model=TokenResponse)
    def signup(body: SignupRequest, session: Session = Depends(db_session)) -> TokenResponse:
        if get_user_by_email(session, body.email):
            raise AppError(409, "email_taken", "Email taken", "An account with this email already exists.")
        user = create_user(session, body.email, body.password, body.full_name)
        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(user.id, user.email, settings),
            refresh_token=create_refresh_token(user.id, user.email, settings),
            expires_in=settings.jwt_access_minutes * 60,
        )

    @application.post("/auth/login", response_model=TokenResponse)
    def login(body: LoginRequest, session: Session = Depends(db_session)) -> TokenResponse:
        user = get_user_by_email(session, body.email)
        if user is None or not verify_password(body.password, user.password_hash):
            raise AppError(401, "invalid_credentials", "Invalid credentials", "Email or password is incorrect.")
        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(user.id, user.email, settings),
            refresh_token=create_refresh_token(user.id, user.email, settings),
            expires_in=settings.jwt_access_minutes * 60,
        )

    @application.post("/auth/refresh", response_model=TokenResponse)
    def refresh(body: RefreshRequest, session: Session = Depends(db_session)) -> TokenResponse:
        try:
            payload = decode_token(body.refresh_token, expected_type="refresh")
        except ValueError as exc:
            raise AppError(401, "unauthorized", "Unauthorized", "Invalid refresh token.") from exc
        user = get_user_by_id(session, payload["sub"])
        if user is None:
            raise AppError(401, "unauthorized", "Unauthorized", "User not found.")
        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(user.id, user.email, settings),
            refresh_token=create_refresh_token(user.id, user.email, settings),
            expires_in=settings.jwt_access_minutes * 60,
        )

    @application.get("/auth/me", response_model=UserResponse)
    def me(user: UserRow = Depends(current_user)) -> UserResponse:
        return user_to_response(user)

    @application.get("/trips", response_model=List[TripSummary])
    def list_trips(
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> List[TripSummary]:
        return service.list_trips(session, user)

    @application.post("/trips", response_model=TripResponse)
    def create_trip(
        body: TripCreateRequest,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.create_trip(session, user, body.constraints, body.preferences_text)

    @application.get("/trips/{trip_id}", response_model=TripResponse)
    def get_trip(
        trip_id: str,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.get_trip(session, user, trip_id)

    @application.post("/trips/{trip_id}/search", response_model=TripResponse)
    def search_trip(
        trip_id: str,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.search(session, user, trip_id)

    @application.post("/trips/{trip_id}/select", response_model=TripResponse)
    def select_offers(
        trip_id: str,
        body: TripSelectRequest,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.select(session, user, trip_id, body.flight_offer_id, body.hotel_offer_id)

    @application.put("/trips/{trip_id}/travelers", response_model=TripResponse)
    def update_travelers(
        trip_id: str,
        body: TravelersUpdateRequest,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.update_travelers(session, user, trip_id, body.travelers)

    @application.post("/trips/{trip_id}/approve", response_model=TripResponse)
    def approve_trip(
        trip_id: str,
        body: TripApproveRequest,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.approve(
            session,
            user,
            trip_id,
            proposal_id=body.proposal_id,
            itinerary_hash=body.itinerary_hash,
            acknowledge_over_budget=body.acknowledge_over_budget,
        )

    @application.post("/trips/{trip_id}/reject", response_model=TripResponse)
    def reject_trip(
        trip_id: str,
        body: TripRejectRequest,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.reject(session, user, trip_id, feedback=body.feedback, research=body.research)

    @application.get("/trips/{trip_id}/status", response_model=TripResponse)
    def trip_status(
        trip_id: str,
        user: UserRow = Depends(current_user),
        session: Session = Depends(db_session),
        service: TripService = Depends(get_service),
    ) -> TripResponse:
        return service.get_trip(session, user, trip_id)

    return application


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("travel_agent.api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
