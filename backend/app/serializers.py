"""Convert ORM rows into API schema objects."""

import json

from app import betting, schemas
from app.models import (
    AnalyticsEvent,
    BetRecord,
    BettingMarket,
    Match,
    Standing,
    Subscription,
    Team,
)


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


def market_summary(market: BettingMarket) -> schemas.MarketSummary:
    match = market.match
    return schemas.MarketSummary(
        match_id=market.match_id,
        status=market.status,
        outcome=market.outcome,
        betting_close_ts=market.betting_close_ts,
        pool_home=market.pool_home,
        pool_away=market.pool_away,
        total_pool=market.pool_home + market.pool_away,
        bet_count=market.bet_count,
        odds_home=betting.gross_decimal_odds(market.pool_home, market.pool_away),
        odds_away=betting.gross_decimal_odds(market.pool_away, market.pool_home),
        market_pubkey=market.market_pubkey,
        stage=match.stage if match else None,
        group_name=match.group_name if match else None,
        utc_date=match.utc_date if match else None,
        home_team_id=match.home_team_id if match else None,
        away_team_id=match.away_team_id if match else None,
        home_team_name=match.home_team.name if match and match.home_team else None,
        away_team_name=match.away_team.name if match and match.away_team else None,
        home_team_crest=match.home_team.crest_url if match and match.home_team else None,
        away_team_crest=match.away_team.crest_url if match and match.away_team else None,
    )


def bet_summary(bet: BetRecord) -> schemas.BetSummary:
    return schemas.BetSummary(
        match_id=bet.match_id,
        wallet=bet.wallet,
        outcome=bet.outcome,
        amount=bet.amount,
        fee_bps=bet.fee_bps,
        claimed=bet.claimed,
        tx_signature=bet.tx_signature,
    )


def subscription_info(sub: Subscription, now) -> schemas.SubscriptionInfo:
    return schemas.SubscriptionInfo(
        wallet=sub.wallet,
        tier=sub.tier,
        expires_at=sub.expires_at,
        active=sub.expires_at > now,
    )


def analytics_event(event: AnalyticsEvent) -> schemas.AnalyticsEventOut:
    return schemas.AnalyticsEventOut(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        ingested_at=event.ingested_at,
        schema_version=event.schema_version,
        match_id=event.match_id,
        wallet=event.wallet,
        tx_signature=event.tx_signature,
        payload=json.loads(event.payload),
    )
