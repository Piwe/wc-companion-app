"""Integration test: betting flow -> analytics extraction feed -> DuckDB star schema.

Drives the *real* extraction endpoint (via TestClient) through the DuckDB ELT module and
asserts the marts + a cross-fact reconciliation. This is the local proof that the schema
in analytics-schema.md holds end-to-end before any Snowflake port.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

duckdb = pytest.importorskip("duckdb")  # skip cleanly if duckdb isn't installed

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AnalyticsEvent, BetRecord, BettingMarket, Match, Team  # noqa: E402
from elt import duckdb_poc  # noqa: E402

ADMIN = {"X-Admin-Token": "change-me"}
USDC = 1_000_000

HOME_TEAM_ID = 990_021
AWAY_TEAM_ID = 990_022
MATCH_ID = 995_021
WALLETS = ["elt-alice", "elt-whale", "elt-bob"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        _seed()
        yield c
        _cleanup()


def _seed():
    db = SessionLocal()
    try:
        db.merge(Team(id=HOME_TEAM_ID, name="Gammaland", tla="GAM"))
        db.merge(Team(id=AWAY_TEAM_ID, name="Deltania", tla="DEL"))
        db.merge(
            Match(
                id=MATCH_ID,
                stage="GROUP_STAGE",
                group_name="Group C",
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
        db.query(BetRecord).filter(BetRecord.match_id == MATCH_ID).delete()
        db.query(BettingMarket).filter(BettingMarket.match_id == MATCH_ID).delete()
        db.query(Match).filter(Match.id == MATCH_ID).delete()
        db.query(Team).filter(Team.id.in_([HOME_TEAM_ID, AWAY_TEAM_ID])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _run_flow(client) -> dict:
    """Create a market, place bets, settle HOME, and claim the winner. Returns the claim."""
    client.post("/api/betting/admin/markets", json={"match_id": MATCH_ID}, headers=ADMIN).raise_for_status()
    for wallet, outcome, amount in [
        ("elt-alice", "HOME", 100 * USDC),
        ("elt-whale", "HOME", 700 * USDC),
        ("elt-bob", "AWAY", 200 * USDC),
    ]:
        client.post(
            "/api/betting/admin/bets",
            json={"match_id": MATCH_ID, "wallet": wallet, "outcome": outcome, "amount": amount},
            headers=ADMIN,
        ).raise_for_status()
    client.post(
        f"/api/betting/admin/markets/{MATCH_ID}/settle", json={"outcome": "HOME"}, headers=ADMIN
    ).raise_for_status()

    # Use the claim preview to drive a realistic claim event.
    preview = client.get(f"/api/betting/markets/{MATCH_ID}/claim/elt-alice").json()
    client.post(
        "/api/betting/admin/claims",
        json={
            "match_id": MATCH_ID,
            "wallet": "elt-alice",
            "payout": preview["payout"],
            "fee": preview["fee"],
        },
        headers=ADMIN,
    ).raise_for_status()
    return preview


def _fetch_via(client):
    def fetch(after_id: int, limit: int) -> list[dict]:
        r = client.get(
            "/api/betting/analytics/events",
            params={"after_id": after_id, "limit": limit},
            headers=ADMIN,
        )
        r.raise_for_status()
        return r.json()

    return fetch


def test_elt_builds_star_schema_and_reconciles(client):
    claim = _run_flow(client)
    con = duckdb_poc.connect(":memory:")
    fetch = _fetch_via(client)

    loaded = duckdb_poc.run_elt(con, fetch)
    assert loaded > 0

    # fact_bet — three placements totalling the 1000-USDC pool for our match.
    bets = con.execute(
        "SELECT COUNT(*), SUM(stake_base) FROM fact_bet WHERE match_id = ?", [MATCH_ID]
    ).fetchone()
    assert bets == (3, 1000 * USDC)

    # fact_settlement — HOME wins, pools captured.
    result, total_pool, winning_pool = con.execute(
        "SELECT result, total_pool_base, winning_pool_base FROM fact_settlement WHERE match_id = ?",
        [MATCH_ID],
    ).fetchone()
    assert (result, total_pool, winning_pool) == ("HOME", 1000 * USDC, 800 * USDC)

    # fact_claim — matches the preview that drove it.
    payout, fee = con.execute(
        "SELECT payout_base, fee_base FROM fact_claim WHERE match_id = ? AND wallet = ?",
        [MATCH_ID, "elt-alice"],
    ).fetchone()
    assert payout == claim["payout"]
    assert fee == claim["fee"]

    # dim_market — built from MARKET_CREATED.
    home_id, away_id = con.execute(
        "SELECT home_team_id, away_team_id FROM dim_market WHERE match_id = ?", [MATCH_ID]
    ).fetchone()
    assert (home_id, away_id) == (HOME_TEAM_ID, AWAY_TEAM_ID)

    # Cross-fact reconciliation: settled pool total == summed stakes (diff 0).
    recon = {row[0]: row for row in duckdb_poc.reconciliation(con)}
    assert MATCH_ID in recon
    assert recon[MATCH_ID][3] == 0  # diff column


def test_elt_incremental_watermark(client):
    con = duckdb_poc.connect(":memory:")
    fetch = _fetch_via(client)

    first = duckdb_poc.load_events(con, fetch)
    assert first > 0
    # No new events between loads => watermark yields zero rows the second time.
    second = duckdb_poc.load_events(con, fetch)
    assert second == 0
