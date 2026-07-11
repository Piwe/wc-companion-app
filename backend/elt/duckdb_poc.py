"""DuckDB proof-of-concept ELT for the betting analytics event log.

Reads the watermark extraction feed (``GET /api/betting/analytics/events``), lands events
into a DuckDB ``raw_betting_events`` table (JSON payload — DuckDB's stand-in for Snowflake's
VARIANT), then builds the star-schema marts from ``analytics-schema.md``. This proves the
model end-to-end locally before any Snowflake spend.

The ``fetch`` callable is injected: ``(after_id, limit) -> list[event dict]``. In tests it
wraps a FastAPI ``TestClient``; the runnable ``run_poc.py`` wraps an HTTP client. The DuckDB
SQL mirrors the reference Snowflake DDL — the only differences are ``JSON``/``json_extract_*``
in place of ``VARIANT``/``:`` path syntax.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

import duckdb

FetchFn = Callable[[int, int], list[dict]]

USDC = 1_000_000  # base units per USDC (6 decimals)

RAW_DDL = """
CREATE TABLE IF NOT EXISTS raw_betting_events (
    event_id       BIGINT PRIMARY KEY,
    event_type     VARCHAR   NOT NULL,
    occurred_at    TIMESTAMP NOT NULL,
    ingested_at    TIMESTAMP NOT NULL,
    schema_version INTEGER   NOT NULL,
    match_id       BIGINT,
    wallet         VARCHAR,
    tx_signature   VARCHAR,
    payload        JSON      NOT NULL
);
"""

# Ordered so dimensions build before facts (not strictly required, but tidy).
MART_SQL: list[tuple[str, str]] = [
    (
        "dim_market",
        """
        CREATE OR REPLACE TABLE dim_market AS
        SELECT
            match_id,
            CAST(json_extract_string(payload, '$.home_team_id') AS BIGINT)      AS home_team_id,
            CAST(json_extract_string(payload, '$.away_team_id') AS BIGINT)      AS away_team_id,
            CAST(json_extract_string(payload, '$.betting_close_ts') AS TIMESTAMP) AS betting_close_ts
        FROM raw_betting_events
        WHERE event_type = 'MARKET_CREATED';
        """,
    ),
    (
        "dim_wallet",
        """
        CREATE OR REPLACE TABLE dim_wallet AS
        SELECT wallet, MIN(occurred_at) AS first_seen, COUNT(*) AS event_count
        FROM raw_betting_events
        WHERE wallet IS NOT NULL
        GROUP BY wallet;
        """,
    ),
    (
        "fact_bet",
        """
        CREATE OR REPLACE TABLE fact_bet AS
        SELECT
            event_id                                                    AS bet_event_key,
            match_id,
            wallet,
            CAST(occurred_at AS DATE)                                   AS date_key,
            json_extract_string(payload, '$.outcome')                   AS outcome,
            CAST(json_extract_string(payload, '$.amount') AS BIGINT)    AS stake_base,
            CAST(json_extract_string(payload, '$.amount') AS BIGINT) / 1000000.0 AS stake_usdc,
            CAST(json_extract_string(payload, '$.fee_bps') AS INTEGER)  AS fee_bps,
            occurred_at,
            tx_signature
        FROM raw_betting_events
        WHERE event_type = 'BET_PLACED';
        """,
    ),
    (
        "fact_settlement",
        """
        CREATE OR REPLACE TABLE fact_settlement AS
        SELECT
            event_id AS settlement_key,
            match_id,
            CASE WHEN event_type = 'MARKET_VOIDED' THEN 'VOID'
                 ELSE json_extract_string(payload, '$.outcome') END           AS result,
            CAST(json_extract_string(payload, '$.pool_home') AS BIGINT)       AS pool_home_base,
            CAST(json_extract_string(payload, '$.pool_away') AS BIGINT)       AS pool_away_base,
            CAST(json_extract_string(payload, '$.total_pool') AS BIGINT)      AS total_pool_base,
            CAST(json_extract_string(payload, '$.winning_pool') AS BIGINT)    AS winning_pool_base,
            occurred_at
        FROM raw_betting_events
        WHERE event_type IN ('MARKET_SETTLED', 'MARKET_VOIDED');
        """,
    ),
    (
        "fact_claim",
        """
        CREATE OR REPLACE TABLE fact_claim AS
        SELECT
            event_id AS claim_key,
            match_id,
            wallet,
            CAST(json_extract_string(payload, '$.payout') AS BIGINT)   AS payout_base,
            CAST(json_extract_string(payload, '$.fee') AS BIGINT)      AS fee_base,
            CAST(json_extract_string(payload, '$.refunded') AS BOOLEAN) AS refunded,
            occurred_at
        FROM raw_betting_events
        WHERE event_type = 'BET_CLAIMED';
        """,
    ),
    (
        "fact_subscription",
        """
        CREATE OR REPLACE TABLE fact_subscription AS
        SELECT
            event_id AS sub_event_key,
            wallet,
            json_extract_string(payload, '$.tier')                          AS tier,
            CAST(json_extract_string(payload, '$.expires_at') AS TIMESTAMP) AS expires_at,
            occurred_at
        FROM raw_betting_events
        WHERE event_type = 'SUBSCRIPTION_CREATED';
        """,
    ),
]


def connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    con.execute(RAW_DDL)
    return con


def load_events(con: duckdb.DuckDBPyConnection, fetch: FetchFn, batch: int = 1000) -> int:
    """Incrementally land new events. Returns the number of rows loaded this run.

    The watermark is ``MAX(event_id)`` already in DuckDB, so re-running is cheap and only
    pulls events newer than what's stored — exactly the Snowflake incremental pattern.
    """
    after = con.execute("SELECT COALESCE(MAX(event_id), 0) FROM raw_betting_events").fetchone()[0]
    loaded = 0
    while True:
        events = fetch(after, batch)
        if not events:
            break
        for e in events:
            con.execute(
                "INSERT OR IGNORE INTO raw_betting_events VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    e["event_id"],
                    e["event_type"],
                    datetime.fromisoformat(e["occurred_at"]),
                    datetime.fromisoformat(e["ingested_at"]),
                    e["schema_version"],
                    e["match_id"],
                    e["wallet"],
                    e["tx_signature"],
                    json.dumps(e["payload"]),
                ],
            )
            after = e["event_id"]
            loaded += 1
        if len(events) < batch:
            break
    return loaded


def build_marts(con: duckdb.DuckDBPyConnection) -> None:
    for _name, sql in MART_SQL:
        con.execute(sql)


def run_elt(con: duckdb.DuckDBPyConnection, fetch: FetchFn) -> int:
    loaded = load_events(con, fetch)
    build_marts(con)
    return loaded


# --- Example analytics (used by the runnable PoC and the integration test) ---


def reconciliation(con: duckdb.DuckDBPyConnection):
    """Per settled (non-void) market: pool total vs summed stakes. ``diff`` should be 0."""
    return con.execute(
        """
        SELECT s.match_id,
               s.total_pool_base,
               COALESCE(SUM(b.stake_base), 0)                      AS staked_base,
               s.total_pool_base - COALESCE(SUM(b.stake_base), 0)  AS diff
        FROM fact_settlement s
        LEFT JOIN fact_bet b ON b.match_id = s.match_id
        WHERE s.result <> 'VOID'
        GROUP BY s.match_id, s.total_pool_base
        ORDER BY s.match_id
        """
    ).fetchall()


def daily_volume(con: duckdb.DuckDBPyConnection):
    return con.execute(
        """
        SELECT date_key,
               COUNT(*)                 AS bets,
               SUM(stake_base) / 1e6    AS volume_usdc
        FROM fact_bet
        GROUP BY date_key
        ORDER BY date_key
        """
    ).fetchall()


def fee_revenue_base(con: duckdb.DuckDBPyConnection) -> int:
    return con.execute("SELECT COALESCE(SUM(fee_base), 0) FROM fact_claim").fetchone()[0]
