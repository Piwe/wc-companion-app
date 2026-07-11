from datetime import datetime

from pydantic import BaseModel


class TeamSummary(BaseModel):
    id: int
    name: str
    tla: str | None = None
    crest_url: str | None = None
    group_name: str | None = None


class StandingRow(BaseModel):
    team_id: int
    team_name: str
    crest_url: str | None = None
    position: int
    played: int
    won: int
    draw: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class MatchSummary(BaseModel):
    id: int
    stage: str
    group_name: str | None = None
    matchday: int | None = None
    status: str
    utc_date: datetime | None = None
    venue: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_team_crest: str | None = None
    away_team_crest: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    winner: str | None = None


class KnockoutStep(BaseModel):
    stage: str
    match_id: int
    opponent_name: str | None = None
    utc_date: datetime | None = None
    result: str  # "won" / "lost" / "draw" / "upcoming"
    score: str | None = None  # e.g. "2-1"


class Progression(BaseModel):
    status: str  # human-readable, e.g. "Advanced — Round of 16"
    qualified: bool
    eliminated: bool


class GroupSummary(BaseModel):
    name: str
    standings: list[StandingRow]


class GroupDetail(BaseModel):
    name: str
    standings: list[StandingRow]
    remaining_fixtures: list[MatchSummary]


class TeamStatus(BaseModel):
    team: TeamSummary
    standing: StandingRow | None = None
    progression: Progression
    upcoming_fixtures: list[MatchSummary]
    knockout_path: list[KnockoutStep]


class TeamMatches(BaseModel):
    team: TeamSummary
    past: list[MatchSummary]
    upcoming: list[MatchSummary]
