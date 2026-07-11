"""Fetch World Cup data from Football-Data.org, normalize it, and store it in SQLite.

A last-good copy of the raw API payload is cached to data/snapshot.json so the app can still
boot (and be developed) when the API is unreachable or no key is configured.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Match, Standing, Team

logger = logging.getLogger("ingestion")

BASE_URL = "https://api.football-data.org/v4"
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot.json"


# --------------------------------------------------------------------------- helpers


def normalize_group(raw: str | None) -> str | None:
    """Convert API group codes like 'GROUP_A' (or 'Group A') into 'Group A'."""
    if not raw:
        return None
    cleaned = raw.replace("_", " ").strip().title()  # "GROUP_A" -> "Group A"
    return cleaned


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# --------------------------------------------------------------------------- fetch


def fetch_from_api(settings: Settings) -> dict:
    """Fetch teams, standings and matches for the configured competition."""
    if not settings.football_data_api_key:
        raise RuntimeError("FOOTBALL_DATA_API_KEY is not set")

    headers = {"X-Auth-Token": settings.football_data_api_key}
    code = settings.competition_code
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
        teams = client.get(f"/competitions/{code}/teams")
        teams.raise_for_status()
        standings = client.get(f"/competitions/{code}/standings")
        standings.raise_for_status()
        matches = client.get(f"/competitions/{code}/matches")
        matches.raise_for_status()

    return {
        "teams": teams.json(),
        "standings": standings.json(),
        "matches": matches.json(),
    }


def save_snapshot(payload: dict) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(payload), encoding="utf-8")


def load_snapshot() -> dict | None:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return None


# --------------------------------------------------------------------------- normalize


def _collect_teams(payload: dict) -> dict[int, dict]:
    """Build one deduped team record per id, merging the /teams list with the group name
    discovered from the standings blocks."""
    teams: dict[int, dict] = {}

    for t in payload.get("teams", {}).get("teams", []):
        tid = t.get("id")
        if tid is None:
            continue
        teams[tid] = {
            "id": tid,
            "name": t.get("name", "Unknown"),
            "tla": t.get("tla"),
            "crest_url": t.get("crest"),
            "group_name": None,
        }

    for block in payload.get("standings", {}).get("standings", []):
        if block.get("type") not in (None, "TOTAL"):
            continue
        group_name = normalize_group(block.get("group"))
        if not group_name:
            continue
        for row in block.get("table", []):
            team = row.get("team", {}) or {}
            tid = team.get("id")
            if tid is None:
                continue
            record = teams.setdefault(
                tid,
                {"id": tid, "name": team.get("name", "Unknown"), "tla": team.get("tla"),
                 "crest_url": team.get("crest"), "group_name": None},
            )
            record["group_name"] = group_name

    return teams


def _store_standings(db: Session, standings_payload: dict) -> None:
    for block in standings_payload.get("standings", []):
        # Group-stage blocks carry a `group`; use only the aggregate ("TOTAL") table.
        if block.get("type") not in (None, "TOTAL"):
            continue
        group_name = normalize_group(block.get("group"))
        if not group_name:
            continue
        for row in block.get("table", []):
            team = row.get("team", {}) or {}
            team_id = team.get("id")
            if team_id is None:
                continue
            db.add(
                Standing(
                    group_name=group_name,
                    team_id=team_id,
                    position=row.get("position", 0),
                    played=row.get("playedGames", 0),
                    won=row.get("won", 0),
                    draw=row.get("draw", 0),
                    lost=row.get("lost", 0),
                    goals_for=row.get("goalsFor", 0),
                    goals_against=row.get("goalsAgainst", 0),
                    goal_difference=row.get("goalDifference", 0),
                    points=row.get("points", 0),
                )
            )


def _store_matches(db: Session, matches_payload: dict) -> None:
    for m in matches_payload.get("matches", []):
        score = m.get("score", {}) or {}
        full_time = score.get("fullTime", {}) or {}
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        venue = m.get("venue")
        db.merge(
            Match(
                id=m["id"],
                stage=m.get("stage", "GROUP_STAGE"),
                group_name=normalize_group(m.get("group")),
                matchday=m.get("matchday"),
                home_team_id=home.get("id"),
                away_team_id=away.get("id"),
                home_score=full_time.get("home"),
                away_score=full_time.get("away"),
                winner=score.get("winner"),
                status=m.get("status", "SCHEDULED"),
                utc_date=parse_utc(m.get("utcDate")),
                venue=venue if venue else "TBD",
            )
        )


def normalize_and_store(db: Session, payload: dict) -> None:
    """Replace all rows with a freshly normalized copy of the payload."""
    db.execute(delete(Standing))
    db.execute(delete(Match))
    db.execute(delete(Team))
    db.flush()

    for record in _collect_teams(payload).values():
        db.add(Team(**record))
    db.flush()

    _store_standings(db, payload.get("standings", {}))
    _store_matches(db, payload.get("matches", {}))
    db.commit()


# --------------------------------------------------------------------------- orchestration


def refresh(db: Session, settings: Settings | None = None) -> str:
    """Fetch (or fall back to snapshot) and store. Returns a short status string."""
    settings = settings or get_settings()
    source = "api"
    try:
        payload = fetch_from_api(settings)
        save_snapshot(payload)
    except Exception as exc:  # noqa: BLE001 — any fetch failure falls back to snapshot
        logger.warning("API fetch failed (%s); falling back to snapshot", exc)
        payload = load_snapshot()
        source = "snapshot"
        if payload is None:
            raise RuntimeError(
                "Could not fetch from API and no snapshot is available. "
                "Set FOOTBALL_DATA_API_KEY in backend/.env."
            ) from exc

    normalize_and_store(db, payload)
    teams = payload.get("teams", {}).get("teams", [])
    matches = payload.get("matches", {}).get("matches", [])
    return f"Refreshed from {source}: {len(teams)} teams, {len(matches)} matches"
