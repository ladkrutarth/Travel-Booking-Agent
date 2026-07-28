"""Auth helpers: password hashing and JWT."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from travel_agent.config import Settings, get_settings
from travel_agent.db import UserRow
from travel_agent.models import UserResponse


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: Dict[str, Any], settings: Settings, expires_delta: timedelta) -> str:
    data = dict(payload)
    data["exp"] = datetime.utcnow() + expires_delta
    data["iat"] = datetime.utcnow()
    return jwt.encode(data, settings.jwt_secret, algorithm="HS256")


def create_access_token(user_id: str, email: str, settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    return _encode(
        {"sub": user_id, "email": email, "type": "access"},
        settings,
        timedelta(minutes=settings.jwt_access_minutes),
    )


def create_refresh_token(user_id: str, email: str, settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    return _encode(
        {"sub": user_id, "email": email, "type": "refresh", "jti": str(uuid4())},
        settings,
        timedelta(days=settings.jwt_refresh_days),
    )


def decode_token(token: str, *, expected_type: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("invalid_token_type")
    if not payload.get("sub"):
        raise ValueError("invalid_token_subject")
    return payload


def get_user_by_email(session: Session, email: str) -> Optional[UserRow]:
    return session.query(UserRow).filter(UserRow.email == email.lower().strip()).one_or_none()


def get_user_by_id(session: Session, user_id: str) -> Optional[UserRow]:
    return session.get(UserRow, user_id)


def create_user(
    session: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
) -> UserRow:
    row = UserRow(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name,
    )
    session.add(row)
    session.flush()
    return row


def user_to_response(row: UserRow) -> UserResponse:
    return UserResponse(id=row.id, email=row.email, full_name=row.full_name)
