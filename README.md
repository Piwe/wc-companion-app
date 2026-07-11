# World Cup 2026 Companion App

A lightweight web app to pick a country and view its **FIFA World Cup 2026** status: group
standings, progression, results, and upcoming fixtures. Data is refreshed daily from a free
football API.

- **Backend:** FastAPI + SQLite, ingests from [Football-Data.org](https://www.football-data.org/)
  (competition code `WC`), with a daily scheduled refresh.
- **Frontend:** React + Vite + TypeScript, TailwindCSS, React Query, Recharts.

## Repository layout

```
backend/    FastAPI service (ingestion, progression logic, REST API)
frontend/   React + Vite single-page app
concept.txt Original concept document
```

## Prerequisites

- Python 3.11+
- Node 18+
- A free **Football-Data.org API key** — sign up at
  <https://www.football-data.org/client/register>. The free tier covers the World Cup
  (10 requests/minute), which is plenty for a daily refresh.

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
cd backend && pytest
```

## Frontend — setup & run

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

The app serves on <http://localhost:5173>.

## Key API endpoints

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
