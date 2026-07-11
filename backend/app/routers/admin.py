from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import ingestion
from app.config import get_settings
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh")
def trigger_refresh(
    x_admin_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    message = ingestion.refresh(db, settings)
    return {"detail": message}
