from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)  # Football-Data team id
    name: Mapped[str] = mapped_column(String, index=True)
    tla: Mapped[str | None] = mapped_column(String(3), nullable=True)
    crest_url: Mapped[str | None] = mapped_column(String, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String, index=True, nullable=True)


class Standing(Base):
    __tablename__ = "standings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    position: Mapped[int] = mapped_column()
    played: Mapped[int] = mapped_column(default=0)
    won: Mapped[int] = mapped_column(default=0)
    draw: Mapped[int] = mapped_column(default=0)
    lost: Mapped[int] = mapped_column(default=0)
    goals_for: Mapped[int] = mapped_column(default=0)
    goals_against: Mapped[int] = mapped_column(default=0)
    goal_difference: Mapped[int] = mapped_column(default=0)
    points: Mapped[int] = mapped_column(default=0)

    team: Mapped[Team] = relationship("Team")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)  # Football-Data match id
    stage: Mapped[str] = mapped_column(String, index=True)
    group_name: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    matchday: Mapped[int | None] = mapped_column(nullable=True)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True, nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True, nullable=True)
    home_score: Mapped[int | None] = mapped_column(nullable=True)
    away_score: Mapped[int | None] = mapped_column(nullable=True)
    winner: Mapped[str | None] = mapped_column(String, nullable=True)  # HOME_TEAM / AWAY_TEAM / DRAW
    status: Mapped[str] = mapped_column(String, index=True)  # SCHEDULED / TIMED / FINISHED / ...
    utc_date: Mapped[datetime | None] = mapped_column(nullable=True)
    venue: Mapped[str | None] = mapped_column(String, nullable=True)

    home_team: Mapped[Team | None] = relationship("Team", foreign_keys=[home_team_id])
    away_team: Mapped[Team | None] = relationship("Team", foreign_keys=[away_team_id])
