from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, serializers
from app.database import get_db
from app.models import Match, Team

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("/team/{team_id}", response_model=schemas.TeamMatches)
def team_matches(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    matches = db.scalars(
        select(Match)
        .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        .order_by(Match.utc_date)
    ).all()

    # Stored datetimes are naive UTC (SQLite), so compare against a naive-UTC "now".
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past, upcoming = [], []
    for m in matches:
        summary = serializers.match_summary(m)
        if m.status == "FINISHED" or (m.utc_date is not None and m.utc_date < now):
            past.append(summary)
        else:
            upcoming.append(summary)

    return schemas.TeamMatches(
        team=serializers.team_summary(team),
        past=past,
        upcoming=upcoming,
    )


@router.get("/{match_id}", response_model=schemas.MatchSummary)
def match_detail(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return serializers.match_summary(match)
