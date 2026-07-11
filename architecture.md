# Architecture — World Cup 2026 Companion App

This document describes how the app is put together: its components, how data flows through the
system, the data model, and the runtime request paths. Diagrams use [Mermaid](https://mermaid.js.org/)
and render natively on GitHub and in most Markdown viewers.

---

## 1. Overview

A lightweight web app where a user picks a country and sees its **FIFA World Cup 2026** status —
group standings, progression, results, and upcoming fixtures. Tournament data is refreshed **once
per day** from a free football API; there is no live/real-time data.

- **Backend:** FastAPI + SQLite (SQLAlchemy 2.0), ingesting from Football-Data.org.
- **Frontend:** React + Vite + TypeScript, TailwindCSS, React Query, Recharts.
- **Shape:** a monorepo with a clean REST boundary between `backend/` and `frontend/`.

**Design principle — derive, don't recompute.** Qualification and knockout progression are read
from the *actual* matches feed (a team with a scheduled or won knockout match has advanced; a team
that lost its latest knockout match is out). We deliberately do **not** reimplement FIFA's
"8 best third-placed teams" algorithm. Group-stage labels are lightweight heuristics used only
while the group stage is live.

---

## 2. System context

How the app sits between the user and the upstream data provider.

```mermaid
graph LR
    User([User / Browser])
    subgraph App["World Cup 2026 Companion (monorepo)"]
        FE["Frontend SPA<br/>React + Vite"]
        BE["Backend API<br/>FastAPI + SQLite"]
    end
    FD[("Football-Data.org<br/>v4 REST API")]

    User -->|HTTPS| FE
    FE -->|"REST / JSON<br/>(CORS)"| BE
    BE -->|"daily fetch<br/>X-Auth-Token"| FD

    classDef ext fill:#fde68a,stroke:#b45309,color:#1c1917;
    classDef comp fill:#dcfce7,stroke:#15803d,color:#14532d;
    class FD ext;
    class FE,BE comp;
```

The frontend never talks to Football-Data.org directly — the backend is the only component holding
the API key, and it caps upstream traffic to a few calls per day.

---

## 3. Container / component view

The two deployables and the responsibilities inside each.

```mermaid
graph TB
    subgraph Frontend["Frontend — React + Vite SPA"]
        direction TB
        Router["React Router<br/>/ · /team/:id · /group/:name · /match/:id"]
        Pages["Pages: Home · Team · Group · Match"]
        Components["Components: SearchBar · GroupList · StandingsTable<br/>MatchList · StatusCard · KnockoutPath · GroupPointsChart"]
        RQ["React Query hooks<br/>(cache, staleTime = 1 day)"]
        Client["API client (fetch wrapper)<br/>src/api/client.ts"]
        Router --> Pages --> Components
        Pages --> RQ --> Client
    end

    subgraph Backend["Backend — FastAPI"]
        direction TB
        Routers["Routers<br/>teams · groups · matches · admin · health"]
        Serializers["serializers.py<br/>ORM → schema"]
        Progression["progression.py<br/>qualification + knockout path (pure)"]
        Ingestion["ingestion.py<br/>fetch · normalize · upsert · snapshot"]
        Scheduler["scheduler.py<br/>APScheduler daily job"]
        Models["models.py (SQLAlchemy ORM)"]
        DB[("SQLite<br/>wc.db")]
        Snap[("data/snapshot.json<br/>last-good payload")]

        Routers --> Serializers --> Models
        Routers --> Progression
        Scheduler --> Ingestion
        Ingestion --> Models
        Ingestion --> Snap
        Models --> DB
    end

    Client -->|"/api/*"| Routers
    Ingestion -->|"HTTP GET"| FD[("Football-Data.org")]

    classDef ext fill:#fde68a,stroke:#b45309,color:#1c1917;
    class FD ext;
```

**Backend module responsibilities**

| Module | Responsibility |
| ------ | -------------- |
| `main.py` | App factory, CORS, router mounting, lifespan (startup ingest + scheduler) |
| `config.py` | `pydantic-settings` config from `.env` (API key, competition code, refresh hour, CORS) |
| `database.py` | SQLAlchemy engine/session, `Base`, `init_db()` |
| `models.py` | ORM entities: `Team`, `Standing`, `Match` |
| `schemas.py` | Pydantic response models (the API contract) |
| `ingestion.py` | Football-Data client → normalize → replace-and-reload; snapshot save/fallback |
| `progression.py` | Pure functions: `compute_progression`, `build_knockout_path`, `humanize_stage` |
| `serializers.py` | ORM → schema conversion shared across routers |
| `scheduler.py` | APScheduler `AsyncIOScheduler` daily refresh job |
| `routers/` | `teams`, `groups`, `matches`, `admin` endpoints |

---

## 4. Daily update workflow

How fresh data gets into the database — on a schedule, at startup, or on demand.

```mermaid
sequenceDiagram
    autonumber
    participant Cron as APScheduler (daily)
    participant Ing as ingestion.refresh()
    participant FD as Football-Data.org
    participant Snap as snapshot.json
    participant DB as SQLite

    Cron->>Ing: trigger at REFRESH_HOUR
    Ing->>FD: GET /competitions/WC/{teams, standings, matches}
    alt API reachable
        FD-->>Ing: JSON payloads
        Ing->>Snap: save last-good payload
    else API unavailable / no key
        Ing->>Snap: load last-good payload
        Note over Ing,Snap: graceful degradation
    end
    Ing->>Ing: normalize (dedupe teams, map rows,<br/>parse dates, derive group names)
    Ing->>DB: DELETE all, then INSERT teams → standings → matches
    Ing-->>Cron: "Refreshed from api/snapshot: N teams, M matches"
```

The same `refresh()` routine has three triggers:

```mermaid
graph LR
    A["Startup<br/>(only if DB empty)"] --> R
    B["Daily cron<br/>(REFRESH_HOUR)"] --> R
    C["POST /api/admin/refresh<br/>(X-Admin-Token)"] --> R
    R["ingestion.refresh(db)"]
```

Ingestion uses a **replace-and-reload** strategy (delete all rows, re-insert the normalized
payload) — simple and correct at this data scale (48 teams, ~104 matches).

---

## 5. Read request flow

What happens when a user opens a team page. React Query caches each response for a day, so repeat
navigation is served from memory.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant P as Team page
    participant H as React Query hook
    participant API as GET /api/teams/{id}
    participant DB as SQLite
    participant Prog as progression.py

    U->>P: navigate to /team/755
    P->>H: useTeamStatus(755)
    alt cached & fresh
        H-->>P: cached TeamStatus
    else fetch
        H->>API: request
        API->>DB: load team, standing, matches
        API->>Prog: compute_progression() + build_knockout_path()
        Prog-->>API: status + qualified/eliminated + path
        API-->>H: TeamStatus JSON
        H-->>P: render StatusCard, KnockoutPath,<br/>StandingsTable, MatchList
    end
```

**API surface**

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/health` | Liveness check |
| GET | `/api/teams?q=` | List / search teams |
| GET | `/api/teams/{id}` | Team status (standing, qualification, knockout path, upcoming) |
| GET | `/api/groups` | All groups with standings |
| GET | `/api/groups/{name}` | Group standings + remaining fixtures |
| GET | `/api/matches/team/{id}` | A team's past + upcoming matches |
| GET | `/api/matches/{id}` | Single match detail |
| POST | `/api/admin/refresh` | Manual re-ingest (requires `X-Admin-Token`) |

---

## 6. Data model

Three tables. `Standing` and `Match` reference `Team`; groups are represented as a string on both
`Team` and `Standing` (no separate table needed).

```mermaid
erDiagram
    TEAM ||--o| STANDING : "has one"
    TEAM ||--o{ MATCH : "home/away"

    TEAM {
        int id PK "Football-Data team id"
        string name
        string tla "3-letter code"
        string crest_url
        string group_name "nullable"
    }
    STANDING {
        int id PK
        string group_name
        int team_id FK
        int position
        int played
        int won
        int draw
        int lost
        int goals_for
        int goals_against
        int goal_difference
        int points
    }
    MATCH {
        int id PK "Football-Data match id"
        string stage "GROUP_STAGE, LAST_16, ..."
        string group_name "nullable (knockout)"
        int matchday "nullable"
        int home_team_id FK
        int away_team_id FK
        int home_score "nullable"
        int away_score "nullable"
        string winner "HOME_TEAM/AWAY_TEAM/DRAW"
        string status "SCHEDULED/FINISHED/..."
        datetime utc_date "naive UTC"
        string venue
    }
```

> **Note on datetimes:** SQLite stores `utc_date` as a **naive** timestamp. All server-side
> time comparisons therefore use a naive-UTC "now"
> (`datetime.now(timezone.utc).replace(tzinfo=None)`) to avoid naive-vs-aware `TypeError`s.

---

## 7. Progression logic

How a team's human-readable status is derived. Knockout truth comes from the matches feed; the
group-stage branch is a lightweight heuristic.

```mermaid
flowchart TD
    Start["compute_progression(team, matches, standing)"] --> HasKO{"has any<br/>knockout match?"}

    HasKO -->|yes| LostLast{"lost latest<br/>finished KO match?"}
    LostLast -->|yes| Elim["Eliminated — {stage}<br/>(qualified=true, eliminated=true)"]
    LostLast -->|no| WonFinal{"won the Final?"}
    WonFinal -->|yes| Champ["Champions 🏆"]
    WonFinal -->|no| Alive{"furthest KO match<br/>finished?"}
    Alive -->|yes| Await["Advanced past {stage}<br/>(awaiting next draw)"]
    Alive -->|no| Playing["Qualified — playing {stage}"]

    HasKO -->|no| GroupDone{"group stage<br/>complete? (played==3)"}
    GroupDone -->|yes| Pos{"final position"}
    Pos -->|"≤ 2"| Adv["Advanced from group"]
    Pos -->|"3"| Third["In contention<br/>(best third-placed)"]
    Pos -->|"4"| GElim["Eliminated — Group Stage"]
    GroupDone -->|no| Live["In qualifying position /<br/>In contention / Must win"]
```

---

## 8. Frontend structure

```mermaid
graph TD
    main["main.tsx<br/>QueryClientProvider + BrowserRouter"] --> App["App.tsx (Routes)"]
    App --> Layout["Layout (header/footer)"]
    App --> Home & Team & Group & Match

    Home --> SearchBar & GroupList
    Team --> StatusCard & KnockoutPath & StandingsTable & MatchList
    Group --> StandingsTable & GroupPointsChart & MatchList
    Match --> Crest

    subgraph Data["Data layer"]
        hooks["api/hooks.ts<br/>useTeams · useTeamStatus · useGroups ·<br/>useGroup · useTeamMatches · useMatch"]
        client["api/client.ts (fetch)"]
        hooks --> client
    end

    Home -.-> hooks
    Team -.-> hooks
    Group -.-> hooks
    Match -.-> hooks
```

State management is intentionally minimal: **React Query** owns all server state (fetching,
caching, loading/error), and there is no separate global store. `staleTime` is one day, matching
the daily refresh cadence.

---

## 9. Deployment view

The MVP targets a single host (concept §9 names Digital Ocean). The frontend builds to static
assets; the backend runs Uvicorn with a local SQLite file.

```mermaid
graph TB
    subgraph Host["Single host / droplet"]
        Static["Static frontend<br/>(vite build → dist/)"]
        Uvicorn["Uvicorn / FastAPI"]
        SQLite[("wc.db")]
        Uvicorn --> SQLite
    end
    Browser([Browser]) --> Static
    Static -->|"/api/*"| Uvicorn
    Uvicorn -->|daily| FD[("Football-Data.org")]

    classDef ext fill:#fde68a,stroke:#b45309,color:#1c1917;
    class FD ext;
```

Because ingestion is a scheduled pull with a JSON snapshot fallback, the app keeps serving the
last-good data even if the upstream API is briefly unavailable.

---

## 10. Key decisions & trade-offs

| Decision | Rationale | Trade-off |
| -------- | --------- | --------- |
| Derive progression from the matches feed | Avoids reimplementing FIFA's best-third-placed algorithm; matches the real bracket | Group-stage labels before the bracket exists are heuristic |
| Replace-and-reload ingestion | Simple, always consistent | Not incremental — fine at 48-team scale, not for large datasets |
| SQLite + single daily refresh | Zero infra, matches "daily static update" scope | Not suited to live/real-time data |
| React Query only (no Redux) | Server state is the only meaningful state | Little benefit if the app later needs rich client state |
| Snapshot fallback | Dev works offline; resilient to API outages | Snapshot can be stale if the API is down for long |
