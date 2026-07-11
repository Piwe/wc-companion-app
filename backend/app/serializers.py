"""Convert ORM rows into API schema objects."""

from app import schemas
from app.models import Match, Standing, Team


def team_summary(team: Team) -> schemas.TeamSummary:
    return schemas.TeamSummary(
        id=team.id,
        name=team.name,
        tla=team.tla,
        crest_url=team.crest_url,
        group_name=team.group_name,
    )


def standing_row(standing: Standing) -> schemas.StandingRow:
    return schemas.StandingRow(
        team_id=standing.team_id,
        team_name=standing.team.name if standing.team else "Unknown",
        crest_url=standing.team.crest_url if standing.team else None,
        position=standing.position,
        played=standing.played,
        won=standing.won,
        draw=standing.draw,
        lost=standing.lost,
        goals_for=standing.goals_for,
        goals_against=standing.goals_against,
        goal_difference=standing.goal_difference,
        points=standing.points,
    )


def match_summary(match: Match) -> schemas.MatchSummary:
    return schemas.MatchSummary(
        id=match.id,
        stage=match.stage,
        group_name=match.group_name,
        matchday=match.matchday,
        status=match.status,
        utc_date=match.utc_date,
        venue=match.venue,
        home_team_id=match.home_team_id,
        away_team_id=match.away_team_id,
        home_team_name=match.home_team.name if match.home_team else None,
        away_team_name=match.away_team.name if match.away_team else None,
        home_team_crest=match.home_team.crest_url if match.home_team else None,
        away_team_crest=match.away_team.crest_url if match.away_team else None,
        home_score=match.home_score,
        away_score=match.away_score,
        winner=match.winner,
    )
