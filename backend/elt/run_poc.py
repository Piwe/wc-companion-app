"""Runnable DuckDB ELT proof-of-concept against a *live* backend.

Usage (from backend/, with the API running):

    python -m elt.run_poc

Env: API_URL (default http://localhost:8000), ADMIN_TOKEN (default change-me),
DUCKDB_PATH (default :memory:). Pulls the analytics feed, builds the marts, and prints
a summary + reconciliation. See analytics-schema.md for the model.
"""

import json
import os
import urllib.parse
import urllib.request

from elt.duckdb_poc import (
    connect,
    daily_volume,
    fee_revenue_base,
    reconciliation,
    run_elt,
)

USDC = 1_000_000


def http_fetch(base_url: str, admin_token: str):
    def fetch(after_id: int, limit: int) -> list[dict]:
        qs = urllib.parse.urlencode({"after_id": after_id, "limit": limit})
        req = urllib.request.Request(
            f"{base_url}/api/betting/analytics/events?{qs}",
            headers={"X-Admin-Token": admin_token},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted local URL)
            return json.loads(resp.read())

    return fetch


def main() -> None:
    base_url = os.environ.get("API_URL", "http://localhost:8000")
    admin_token = os.environ.get("ADMIN_TOKEN", "change-me")
    duckdb_path = os.environ.get("DUCKDB_PATH", ":memory:")

    con = connect(duckdb_path)
    loaded = run_elt(con, http_fetch(base_url, admin_token))

    raw = con.execute("SELECT COUNT(*) FROM raw_betting_events").fetchone()[0]
    print(f"Loaded {loaded} new events (raw total: {raw}) from {base_url}\n")

    for table in ("fact_bet", "fact_settlement", "fact_claim", "fact_subscription"):
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<18} {n} rows")

    print(f"\nFee revenue: {fee_revenue_base(con) / USDC:.2f} USDC")

    print("\nDaily betting volume:")
    for date_key, bets, volume in daily_volume(con):
        print(f"  {date_key}  {bets:>3} bets  {volume:>12.2f} USDC")

    print("\nReconciliation (settled markets — diff should be 0):")
    rows = reconciliation(con)
    if not rows:
        print("  (no settled markets yet)")
    for match_id, total_pool, staked, diff in rows:
        flag = "OK" if diff == 0 else "MISMATCH"
        print(
            f"  match {match_id}: pool={total_pool / USDC:.2f} "
            f"staked={staked / USDC:.2f} diff={diff / USDC:.2f} [{flag}]"
        )


if __name__ == "__main__":
    main()
