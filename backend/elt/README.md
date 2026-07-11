# DuckDB ELT proof-of-concept

Validates the betting analytics star schema **locally** — no Snowflake required. It consumes the
same watermark extraction feed a real warehouse loader would (`GET /api/betting/analytics/events`),
lands events into DuckDB, and builds the fact/dim marts from
[`../../analytics-schema.md`](../../analytics-schema.md).

DuckDB is used precisely because it's the cheap local analogue of Snowflake: columnar, a `JSON`
type standing in for `VARIANT`, and near-identical SQL. Proving the model here de-risks the
Snowflake port to a mechanical translation.

## Run it

```bash
pip install duckdb                 # once
cd backend
uvicorn app.main:app --reload      # terminal 1: the API
python -m elt.run_poc              # terminal 2: the ELT
```

Env vars: `API_URL` (default `http://localhost:8000`), `ADMIN_TOKEN` (default `change-me`),
`DUCKDB_PATH` (default `:memory:`; set a file path to persist the warehouse).

To generate data first, create a market and post some bets/settlement/claims via the
`/api/betting/admin/*` endpoints (see `betting-program-spec.md` / the API docs at `/docs`).

## What it produces

- `raw_betting_events` — the landing table (JSON payload ≈ Snowflake VARIANT)
- `dim_market`, `dim_wallet`
- `fact_bet`, `fact_settlement`, `fact_claim`, `fact_subscription`
- example analytics: fee revenue, daily volume, and a **reconciliation** check
  (settled-market pool total == summed stakes)

## Mapping to Snowflake

| DuckDB (here) | Snowflake (target) |
|---------------|--------------------|
| `JSON` column + `json_extract_string(payload, '$.x')` | `VARIANT` column + `payload:x` |
| `INSERT OR IGNORE` incremental by `MAX(event_id)` | `COPY`/Snowpipe + `MERGE` on `event_id` |
| local file / `:memory:` | `RAW` / `ANALYTICS` schemas |

The module (`duckdb_poc.py`) is import-friendly and injected with a `fetch(after_id, limit)`
callable, so the integration test drives it with a `TestClient` instead of HTTP.
