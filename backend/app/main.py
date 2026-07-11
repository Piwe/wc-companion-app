import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app import ingestion
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Team
from app.routers import admin, groups, matches, teams
from app.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()

    # Ingest on startup only if the database is empty.
    db = SessionLocal()
    try:
        team_count = db.scalar(select(func.count()).select_from(Team)) or 0
        if team_count == 0:
            try:
                message = ingestion.refresh(db, settings)
                logger.info("Startup ingestion: %s", message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Startup ingestion skipped: %s", exc)
    finally:
        db.close()

    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="World Cup 2026 Companion API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router)
app.include_router(groups.router)
app.include_router(matches.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
