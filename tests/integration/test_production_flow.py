"""Production auth + booking flow integration tests."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ["AMADEUS_MOCK"] = "true"
os.environ["FLIGHT_SOURCES"] = "mock"
os.environ["OPENWEATHER_MOCK"] = "true"
os.environ["GOOGLE_PLACES_MOCK"] = "true"
os.environ["KILL_SWITCH"] = "false"
os.environ["JWT_SECRET"] = "test-secret"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'prod.db'}")
    monkeypatch.setenv("AMADEUS_MOCK", "true")
    monkeypatch.setenv("FLIGHT_SOURCES", "mock")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    from travel_agent.config import get_settings

    get_settings.cache_clear()
    import travel_agent.db as dbmod

    dbmod.reset_engine()
    dbmod.init_db()

    from travel_agent.api.main import create_app, get_service
    from travel_agent.service import TripService

    application = create_app()
    service = TripService()
    application.dependency_overrides[get_service] = lambda: service
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()
    get_settings.cache_clear()
    dbmod.reset_engine()


def _auth(client: TestClient, email: str = "alex@example.com") -> dict:
    signup = client.post(
        "/auth/signup",
        json={"email": email, "password": "password123", "full_name": "Alex"},
    )
    assert signup.status_code == 200, signup.text
    token = signup.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_signup_login_and_me(client):
    headers = _auth(client)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alex@example.com"
    bad = client.post("/auth/login", json={"email": "alex@example.com", "password": "wrongpass1"})
    assert bad.status_code == 401


def test_trip_ownership_isolation(client):
    h1 = _auth(client, "one@example.com")
    h2 = _auth(client, "two@example.com")
    created = client.post(
        "/trips",
        headers=h1,
        json={
            "constraints": {
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": "2026-09-01",
                "return_date": "2026-09-05",
                "adults": 1,
                "budget_usd": 2000,
                "travelers": [],
            }
        },
    )
    assert created.status_code == 200
    trip_id = created.json()["trip_id"]
    denied = client.get(f"/trips/{trip_id}", headers=h2)
    assert denied.status_code == 404


def test_full_booking_happy_path(client):
    headers = _auth(client)
    created = client.post(
        "/trips",
        headers=headers,
        json={
            "constraints": {
                "origin": "JFK",
                "destination": "LAX",
                "destination_city": "Los Angeles",
                "departure_date": "2026-09-01",
                "return_date": "2026-09-05",
                "adults": 1,
                "budget_usd": 2000,
                "travelers": [],
            }
        },
    )
    trip_id = created.json()["trip_id"]
    searched = client.post(f"/trips/{trip_id}/search", headers=headers)
    assert searched.status_code == 200
    body = searched.json()
    assert body["state"] == "COMPARE"
    assert body["flight_offers"]
    assert body["hotel_offers"]
    tools = {e["tool"] for e in body.get("tool_calls", [])}
    assert "search_google_flights" in tools
    assert "search_hotels_booking_com" in tools
    assert body["flight_offers"][0].get("source")

    selected = client.post(
        f"/trips/{trip_id}/select",
        headers=headers,
        json={
            "flight_offer_id": body["flight_offers"][0]["offer_id"],
            "hotel_offer_id": body["hotel_offers"][0]["offer_id"],
        },
    )
    assert selected.status_code == 200
    assert selected.json()["state"] == "TRAVELERS"

    travelers = client.put(
        f"/trips/{trip_id}/travelers",
        headers=headers,
        json={
            "travelers": [
                {
                    "first_name": "Alex",
                    "last_name": "Traveler",
                    "email": "alex@example.com",
                    "date_of_birth": "1990-01-01",
                }
            ]
        },
    )
    assert travelers.status_code == 200
    assert travelers.json()["state"] == "AWAIT_APPROVAL"
    proposal = travelers.json()["proposal"]

    approved = client.post(
        f"/trips/{trip_id}/approve",
        headers=headers,
        json={
            "proposal_id": proposal["proposal_id"],
            "itinerary_hash": proposal["itinerary_hash"],
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "CONFIRM"
    assert len(approved.json()["bookings"]) == 2


def test_over_budget_requires_ack(client):
    headers = _auth(client, "budget@example.com")
    created = client.post(
        "/trips",
        headers=headers,
        json={
            "constraints": {
                "origin": "ORD",
                "destination": "LHR",
                "departure_date": "2026-10-01",
                "return_date": "2026-10-08",
                "adults": 1,
                "budget_usd": 50,
                "travelers": [],
            }
        },
    )
    trip_id = created.json()["trip_id"]
    searched = client.post(f"/trips/{trip_id}/search", headers=headers).json()
    flight_id = searched["flight_offers"][0]["offer_id"]
    hotel_id = searched["hotel_offers"][0]["offer_id"]
    selected = client.post(
        f"/trips/{trip_id}/select",
        headers=headers,
        json={"flight_offer_id": flight_id, "hotel_offer_id": hotel_id},
    ).json()
    assert selected["proposal"]["within_budget"] is False
    client.put(
        f"/trips/{trip_id}/travelers",
        headers=headers,
        json={"travelers": [{"first_name": "A", "last_name": "B"}]},
    )
    proposal = client.get(f"/trips/{trip_id}", headers=headers).json()["proposal"]
    blocked = client.post(
        f"/trips/{trip_id}/approve",
        headers=headers,
        json={
            "proposal_id": proposal["proposal_id"],
            "itinerary_hash": proposal["itinerary_hash"],
            "acknowledge_over_budget": False,
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "over_budget_ack_required"


def test_expired_proposal(client):
    headers = _auth(client, "expire@example.com")
    created = client.post(
        "/trips",
        headers=headers,
        json={
            "constraints": {
                "origin": "BOS",
                "destination": "MIA",
                "departure_date": "2026-08-01",
                "return_date": "2026-08-04",
                "adults": 1,
                "budget_usd": 1500,
                "travelers": [],
            }
        },
    )
    trip_id = created.json()["trip_id"]
    searched = client.post(f"/trips/{trip_id}/search", headers=headers).json()
    client.post(
        f"/trips/{trip_id}/select",
        headers=headers,
        json={
            "flight_offer_id": searched["flight_offers"][0]["offer_id"],
            "hotel_offer_id": searched["hotel_offers"][0]["offer_id"],
        },
    )
    client.put(
        f"/trips/{trip_id}/travelers",
        headers=headers,
        json={"travelers": [{"first_name": "A", "last_name": "B"}]},
    )
    from travel_agent.db import session_factory
    from travel_agent.db import repository as repo

    session = session_factory()
    try:
        repo.update_trip(
            session,
            trip_id,
            proposal_expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        session.commit()
    finally:
        session.close()

    trip = client.get(f"/trips/{trip_id}", headers=headers).json()
    assert trip["state"] == "EXPIRED"
