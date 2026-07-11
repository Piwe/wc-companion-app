from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, serializers
from app.database import get_db
from app.models import Match, Standing, Team
from app.progression import build_knockout_path, compute_progression

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[schemas.TeamSummary])
def list_teams(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Team)
    if q:
        stmt = stmt.where(Team.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Team.name)
    return [serializers.team_summary(t) for t in db.scalars(stmt).all()]


@router.get("/{team_id}", response_model=schemas.TeamStatus)
def team_status(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    standing = db.scalars(select(Standing).where(Standing.team_id == team_id)).first()
    matches = db.scalars(
        select(Match)
        .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        .order_by(Match.utc_date)
    ).all()

    team_names = {t.id: t.name for t in db.scalars(select(Team)).all()}
    progression = compute_progression(team_id, matches, standing)
    knockout_path = build_knockout_path(team_id, matches, team_names)

    # Stored datetimes are naive UTC (SQLite), so compare against a naive-UTC "now".
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upcoming = [
        serializers.match_summary(m)
        for m in matches
        if m.status != "FINISHED" and (m.utc_date is None or m.utc_date >= now)
    ]

    return schemas.TeamStatus(
        team=serializers.team_summary(team),
        standing=serializers.standing_row(standing) if standing else None,
        progression=schemas.Progression(**progression),
        upcoming_fixtures=upcoming[:5],
        knockout_path=[schemas.KnockoutStep(**step) for step in knockout_path],
    )
