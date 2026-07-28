"""FastAPI auth dependencies."""

from __future__ import annotations

from typing import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from travel_agent.auth import decode_token, get_user_by_id, user_to_response
from travel_agent.db import UserRow, get_session
from travel_agent.errors import AppError
from travel_agent.models import UserResponse

bearer = HTTPBearer(auto_error=False)


def db_session() -> Generator[Session, None, None]:
    yield from get_session()


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    session: Session = Depends(db_session),
) -> UserRow:
    if creds is None or not creds.credentials:
        raise AppError(401, "unauthorized", "Unauthorized", "Authentication required.")
    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except ValueError as exc:
        raise AppError(401, "unauthorized", "Unauthorized", "Invalid or expired access token.") from exc
    user = get_user_by_id(session, payload["sub"])
    if user is None:
        raise AppError(401, "unauthorized", "Unauthorized", "User not found.")
    return user


def current_user_response(user: UserRow = Depends(current_user)) -> UserResponse:
    return user_to_response(user)
