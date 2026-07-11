"""Tests for the betting layer: parimutuel math + the market/bet/settle API flow.

The API tests seed their own synthetic teams/match directly via the DB session, so they
do not depend on the Football-Data snapshot.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import betting
from app.database import SessionLocal
from app.main import app
from app.models import BetRecord, BettingMarket, Match, Subscription, Team

ADMIN = {"X-Admin-Token": "change-me"}
USDC = 1_000_000  # 1 USDC in base units

# Synthetic ids kept far away from real Football-Data ids.
HOME_TEAM_ID = 990_001
AWAY_TEAM_ID = 990_002
MATCH_ID = 995_001


# --- Pure math (spec §6) -----------------------------------------------------


def test_settle_payout_matches_spec_example():
    # Pools: home 800, away 200 USDC. Alice staked 100 on HOME at 2% (premium) fee.
    p = betting.settle_payout(
        stake=100 * USDC, winning_pool=800 * USDC, losing_pool=200 * USDC, fee_bps=200
    )
    assert p.profit == 25 * USDC
    assert p.fee == 500_000  # 0.5 USDC
    assert p.payout == 124 * USDC + 500_000


def test_settle_payout_one_sided_returns_stake():
    # No losers -> profit 0, fee 0, just the stake back.
    p = betting.settle_payout(stake=50 * USDC, winning_pool=50 * USDC, losing_pool=0, fee_bps=500)
    assert (p.profit, p.fee, p.payout) == (0, 0, 50 * USDC)


def test_gross_decimal_odds():
    assert betting.gross_decimal_odds(800 * USDC, 200 * USDC) == 1.25
    assert betting.gross_decimal_odds(200 * USDC, 800 * USDC) == 5.0
    assert betting.gross_decimal_odds(0, 100 * USDC) is None


def test_preview_adds_stake_to_pool():
    # Betting 100 into an empty HOME pool vs 200 on AWAY: your 100 is the whole winning pool.
    p = betting.preview_payout(stake=100 * USDC, side_pool=0, other_pool=200 * USDC, fee_bps=0)
    assert p.profit == 200 * USDC  # take the entire losing pool
    assert p.payout == 300 * USDC


# --- API flow ----------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # triggers lifespan -> init_db (creates betting tables)
        _seed(c)
        yield c
        _cleanup()


def _seed(_c):
    db = SessionLocal()
    try:
        db.merge(Team(id=HOME_TEAM_ID, name="Testland", tla="TST"))
        db.merge(Team(id=AWAY_TEAM_ID, name="Probaria", tla="PRB"))
        db.merge(
            Match(
                id=MATCH_ID,
                stage="GROUP_STAGE",
                group_name="Group Z",
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
        db.query(BetRecord).filter(BetRecord.match_id == MATCH_ID).delete()
        db.query(BettingMarket).filter(BettingMarket.match_id == MATCH_ID).delete()
        db.query(Subscription).filter(
            Subscription.wallet.in_(["alice", "whale", "bob"])
        ).delete(synchronize_session=False)
        db.query(Match).filter(Match.id == MATCH_ID).delete()
        db.query(Team).filter(Team.id.in_([HOME_TEAM_ID, AWAY_TEAM_ID])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def test_full_market_flow(client):
    # 1. Create the market.
    r = client.post("/api/betting/admin/markets", json={"match_id": MATCH_ID}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "OPEN"

    # 2. Record bets: pool_home = 800 (alice premium 100 + whale 700), pool_away = 200 (bob).
    client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "alice", "outcome": "HOME", "amount": 100 * USDC, "fee_bps": 200},
        headers=ADMIN,
    ).raise_for_status()
    client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "whale", "outcome": "HOME", "amount": 700 * USDC},
        headers=ADMIN,
    ).raise_for_status()
    client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "bob", "outcome": "AWAY", "amount": 200 * USDC},
        headers=ADMIN,
    ).raise_for_status()

    # 3. Market reflects pools, odds, and bet count.
    market = client.get(f"/api/betting/markets/{MATCH_ID}").json()
    assert market["pool_home"] == 800 * USDC
    assert market["pool_away"] == 200 * USDC
    assert market["bet_count"] == 3
    assert market["odds_home"] == 1.25
    assert market["odds_away"] == 5.0

    # 4. Hedging the opposite side is rejected.
    dup = client.post(
        "/api/betting/admin/bets",
        json={"match_id": MATCH_ID, "wallet": "alice", "outcome": "AWAY", "amount": USDC},
        headers=ADMIN,
    )
    assert dup.status_code == 409

    # 5. Settle HOME (explicit outcome).
    r = client.post(
        f"/api/betting/admin/markets/{MATCH_ID}/settle", json={"outcome": "HOME"}, headers=ADMIN
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SETTLED"
    assert r.json()["outcome"] == "HOME"

    # 6. Claim previews: alice wins per the spec example, bob loses.
    alice = client.get(f"/api/betting/markets/{MATCH_ID}/claim/alice").json()
    assert alice["result"] == "won"
    assert alice["payout"] == 124 * USDC + 500_000
    assert alice["fee"] == 500_000

    bob = client.get(f"/api/betting/markets/{MATCH_ID}/claim/bob").json()
    assert bob["result"] == "lost"
    assert bob["payout"] == 0


def test_preview_endpoint(client):
    # Betting into the existing HOME pool (800) against AWAY (200).
    r = client.get(
        f"/api/betting/markets/{MATCH_ID}/preview",
        params={"outcome": "HOME", "amount": 100 * USDC, "tier": "PREMIUM"},
    )
    # Market is already settled by the flow test if it ran first, but preview is state-independent
    # of settlement (reads pools only), so this is safe regardless of order.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stake"] == 100 * USDC
    assert body["projected_payout"] > 0


def test_subscription_record_and_active_flag(client):
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = client.post(
        "/api/betting/admin/subscriptions",
        json={"wallet": "alice", "tier": "PREMIUM", "expires_at": future},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "PREMIUM"
    assert body["active"] is True

    got = client.get("/api/betting/wallets/alice/subscription").json()
    assert got["active"] is True


def test_admin_endpoints_require_token(client):
    assert client.post("/api/betting/admin/markets", json={"match_id": MATCH_ID}).status_code == 401
