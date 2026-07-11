from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, serializers
from app.database import get_db
from app.models import Match, Standing

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _group_standings(db: Session, name: str) -> list[schemas.StandingRow]:
    rows = db.scalars(
        select(Standing).where(Standing.group_name == name).order_by(Standing.position)
    ).all()
    return [serializers.standing_row(r) for r in rows]


@router.get("", response_model=list[schemas.GroupSummary])
def list_groups(db: Session = Depends(get_db)):
    names = db.scalars(
        select(Standing.group_name).distinct().order_by(Standing.group_name)
    ).all()
    return [
        schemas.GroupSummary(name=name, standings=_group_standings(db, name))
        for name in names
        if name
    ]


@router.get("/{name}", response_model=schemas.GroupDetail)
def group_detail(name: str, db: Session = Depends(get_db)):
    standings = _group_standings(db, name)
    if not standings:
        raise HTTPException(status_code=404, detail="Group not found")

    remaining = db.scalars(
        select(Match)
        .where(Match.group_name == name, Match.status != "FINISHED")
        .order_by(Match.utc_date)
    ).all()

    return schemas.GroupDetail(
        name=name,
        standings=standings,
        remaining_fixtures=[serializers.match_summary(m) for m in remaining],
    )
