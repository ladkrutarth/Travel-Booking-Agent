"""SQLAlchemy models and session helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Generator, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from travel_agent.config import get_settings


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TripRow(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="INTAKE")
    constraints_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    flight_offers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hotel_offers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ranked_pairs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_flight_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    selected_hotel_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    weather_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviews_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposal_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposal_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bookings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    approval_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trip_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


_engine = None
_SessionLocal = None


def reset_engine() -> None:
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_factory() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()
