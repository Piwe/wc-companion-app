# World Cup 2026 Companion App

A lightweight web app to pick a country and view its **FIFA World Cup 2026** status: group
standings, progression, results, and upcoming fixtures. Data is refreshed daily from a free
football API. An optional **Solana betting** layer and a **warehouse-ready analytics** pipeline
are built on top.

- **Backend:** FastAPI + SQLite, ingests from [Football-Data.org](https://www.football-data.org/)
  (competition code `WC`), with a daily scheduled refresh.
- **Frontend:** React + Vite + TypeScript, TailwindCSS, React Query, Recharts.
- **Betting (add-on):** parimutuel match-winner betting in USDC on Solana devnet, with tiered
  subscriptions — an Anchor program plus a backend mirror/oracle layer and a betting UI.
- **Analytics (add-on):** an append-only event log with a DuckDB ELT proof-of-concept, designed
  to port to Snowflake.

## Repository layout

```
backend/          FastAPI service (ingestion, progression, REST API, betting layer)
  app/            application code (routers, models, betting.py, analytics.py, ...)
  elt/            DuckDB ELT proof-of-concept for betting analytics
  tests/          pytest suite
frontend/         React + Vite single-page app (incl. the Betting page)
anchor/           wc_betting Anchor program (Rust) — Solana smart contract
betting-program-spec.md   full on-chain program specification
analytics-schema.md       analytics star schema + Snowflake DDL / ELT design
architecture.md           system architecture + diagrams (incl. section 11 betting)
```

## Prerequisites

- Python 3.11+
- Node 18+
- A free **Football-Data.org API key** — sign up at
  <https://www.football-data.org/client/register>. The free tier covers the World Cup.
- *(Betting on-chain only)* the Solana/Anchor toolchain — see [`anchor/README.md`](./anchor/README.md).

## Backend — setup & run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste your API key into FOOTBALL_DATA_API_KEY
uvicorn app.main:app --reload
```

The API serves on <http://localhost:8000>. Interactive docs at <http://localhost:8000/docs>.

On first startup (with an empty DB) the app ingests live data. If the API is unreachable it
falls back to the last-good snapshot in `backend/data/snapshot.json`.

Run tests:

```bash
cd backend && pytest        # 28 tests: app + betting + analytics + ELT
```

## Frontend — setup & run

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

The app serves on <http://localhost:5173>. The **Betting** page is at `/betting`.

## Core API endpoints

| Method | Path                       | Purpose                                    |
| ------ | -------------------------- | ------------------------------------------ |
| GET    | `/api/health`              | Liveness check                             |
| GET    | `/api/teams?q=`            | List / search teams                        |
| GET    | `/api/teams/{id}`          | Team status (standing, qualification, path)|
| GET    | `/api/groups`              | All 12 groups with standings               |
| GET    | `/api/groups/{name}`       | Group standings + remaining fixtures       |
| GET    | `/api/matches/team/{id}`   | A team's past + upcoming matches           |
| GET    | `/api/matches/{id}`        | Single match detail                        |
| POST   | `/api/admin/refresh`       | Manual re-ingest (requires `ADMIN_TOKEN`)  |

## Betting layer

Parimutuel betting on the match winner (HOME/AWAY only; a DRAW voids the market and refunds
everyone), settled in USDC. Subscriptions gate betting and come in two tiers (Standard, Premium —
Premium pays a reduced house fee). Full design in
[`betting-program-spec.md`](./betting-program-spec.md).

- On-chain custody + payouts live in the `wc_betting` **Anchor program** (`anchor/`).
- The backend is the **oracle** (maps `Match.winner`/`FINISHED` → settle/void) and read-model
  **indexer**; it never custodies funds.

| Method | Path                                        | Purpose                          |
| ------ | ------------------------------------------- | -------------------------------- |
| GET    | `/api/betting/markets`                      | Open markets with live odds/pools|
| GET    | `/api/betting/markets/{id}/preview`         | Parimutuel payout projection     |
| GET    | `/api/betting/wallets/{w}/bets`             | A wallet's bets                  |
| POST   | `/api/betting/admin/markets`                | Create a market (admin)          |
| POST   | `/api/betting/admin/markets/{id}/settle`    | Settle / void (oracle)           |
| GET    | `/api/betting/analytics/events?after_id=`   | Analytics extraction feed        |

> ⚠️ **On-chain betting is not live.** The Anchor program is committed as source only and has
> not been compiled/deployed (it needs the Solana toolchain). The UI shows live odds and payout
> previews but disables real bet/claim actions. See [`architecture.md`](./architecture.md) section 11.1.

## Analytics

Every betting state change is written to an append-only `analytics_events` log (in the same
transaction as the mirror update). A DuckDB **ELT proof-of-concept** (`backend/elt/`) consumes the
extraction feed and builds a star schema (facts + dims), validating the model locally before any
Snowflake spend. Design and Snowflake DDL in [`analytics-schema.md`](./analytics-schema.md); how to
run the PoC in [`backend/elt/README.md`](./backend/elt/README.md).

## Deployment

The MVP targets a single host: the frontend builds to static assets (`vite build → dist/`) and the
backend runs Uvicorn with a local SQLite file. See [`architecture.md`](./architecture.md) section 9.

## Credits

- **Piwe** ([twala.simphiwe@gmail.com](mailto:twala.simphiwe@gmail.com)) — author & maintainer
- **Claude** (Anthropic — Claude Code, Opus 4.8) — co-developer

The betting framework, analytics pipeline, and supporting docs were built in collaboration with
Claude Code; see the `Co-Authored-By` trailers in the commit history.
