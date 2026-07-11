"""Tests for the analytics event log: emission through the betting flow, idempotent
dedupe, and the watermark-based extraction feed used by the warehouse ELT."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import analytics
from app.database import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, BetRecord, BettingMarket, Match, Subscription, Team

ADMIN = {"X-Admin-Token": "change-me"}
USDC = 1_000_000

HOME_TEAM_ID = 990_011
AWAY_TEAM_ID = 990_012
MATCH_ID = 995_011
WALLETS = ["ana-alice", "ana-bob"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        _seed()
        yield c
        _cleanup()


def _seed():
    db = SessionLocal()
    try:
        db.merge(Team(id=HOME_TEAM_ID, name="Alphaland", tla="ALP"))
        db.merge(Team(id=AWAY_TEAM_ID, name="Betamar", tla="BET"))
        db.merge(
            Match(
                id=MATCH_ID,
                stage="GROUP_STAGE",
                group_name="Group A",
                home_team_id=HOME_TEAM_ID,
                away_team_id=AWAY_TEAM_ID,
                status="SCHEDULED",
                utc_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
            )
        )
        db.commit()
    finally:
        db.close()


def _cleanup():
    db = SessionLocal()
    try:
        db.query(AnalyticsEvent).filter(AnalyticsEvent.match_id == MATCH_ID).delete()
        db.query(AnalyticsEvent).filter(
            AnalyticsEvent.dedupe_key == "UNIT_TEST_DEDUPE"
        ).delete(synchronize_session=False)
        db.query(BetRecord).filter(BetRecord.match_id == MATCH_ID).delete()
        db.query(BettingMarket).filter(BettingMarket.match_id == MATCH_ID).delete()
        db.query(Subscription).filter(Subscription.wallet.in_(WALLETS)).delete(
            synchronize_session=False
        )
        db.query(Match).filter(Match.id == MATCH_ID).delete()
        db.query(Team).filter(Team.id.in_([HOME_TEAM_ID, AWAY_TEAM_ID])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _types_for_match(client) -> list[str]:
    events = client.get("/api/betting/analytics/events", headers=ADMIN).json()
    return [e["event_type"] for e in events if e["match_id"] == MATCH_ID]


def test_emit_dedupe_is_idempotent(client):  # client fixture ensures init_db() has run
    db = SessionLocal()
    try:
        e1 = analytics.emit(db, analytics.MARKET_CREATED, {"x": 1}, dedupe_key="UNIT_TEST_DEDUPE")
        db.commit()
        e2 = analytics.emit(db, analytics.MARKET_CREATED, {"x": 2}, dedupe_key="UNIT_TEST_DEDUPE")
        db.commit()
        assert e1.event_id == e2.event_id  # second call returns the existing row
        count = (
            db.query(AnalyticsEvent)
            .filter(AnalyticsEvent.dedupe_key == "UNIT_TEST_DEDUPE")
            .count()
        )
        assert count == 1
    finally:
        db.close()


def test_flow_emits_ordered_events(client):
    client.post("/api/betting/admin/markets", json={"match_id": MATCH_ID}, headers=ADMIN).raise_for_status()

    client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "ana-alice", "outcome": "HOME", "amount": 100 * USDC},
        headers=ADMIN,
    ).raise_for_status()
    client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "ana-bob", "outcome": "AWAY", "amount": 50 * USDC},
        headers=ADMIN,
    ).raise_for_status()
    client.post(
        f"/api/betting/admin/markets/{MATCH_ID}/settle", json={"outcome": "HOME"}, headers=ADMIN
    ).raise_for_status()
    client.post(
        "/api/betting/admin/claims",
        json={"match_id": MATCH_ID, "wallet": "ana-alice", "payout": 150 * USDC, "fee": 0},
        headers=ADMIN,
    ).raise_for_status()

    types = _types_for_match(client)
    assert types == [
        "MARKET_CREATED",
        "BET_PLACED",
        "BET_PLACED",
        "MARKET_SETTLED",
        "BET_CLAIMED",
    ]


def test_event_payload_is_warehouse_shaped(client):
    events = client.get(
        "/api/betting/analytics/events",
        params={"event_type": "MARKET_SETTLED"},
        headers=ADMIN,
    ).json()
    ev = next(e for e in events if e["match_id"] == MATCH_ID)
    # Money is integer base units (exact), payload is a nested object (-> Snowflake VARIANT).
    assert ev["payload"]["outcome"] == "HOME"
    assert ev["payload"]["total_pool"] == 150 * USDC
    assert ev["schema_version"] == analytics.SCHEMA_VERSION
    assert isinstance(ev["payload"]["winning_pool"], int)


def test_watermark_extraction(client):
    everything = client.get("/api/betting/analytics/events", headers=ADMIN).json()
    assert everything == sorted(everything, key=lambda e: e["event_id"])  # monotonic order

    # after_id excludes everything up to and including that id.
    last_id = everything[-1]["event_id"]
    tail = client.get(
        "/api/betting/analytics/events", params={"after_id": last_id}, headers=ADMIN
    ).json()
    assert tail == []


def test_extraction_requires_admin(client):
    assert client.get("/api/betting/analytics/events").status_code == 401
