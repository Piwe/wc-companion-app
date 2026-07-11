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


# --- Betting layer -----------------------------------------------------------


class MarketSummary(BaseModel):
    match_id: int
    status: str  # OPEN / SETTLED / VOIDED
    outcome: str | None = None  # HOME / AWAY
    betting_close_ts: datetime | None = None
    pool_home: int  # USDC base units
    pool_away: int
    total_pool: int
    bet_count: int
    odds_home: float | None = None  # gross decimal odds; None if that side is empty
    odds_away: float | None = None
    market_pubkey: str | None = None
    # denormalised match context for display
    stage: str | None = None
    group_name: str | None = None
    utc_date: datetime | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_team_crest: str | None = None
    away_team_crest: str | None = None


class BetSummary(BaseModel):
    match_id: int
    wallet: str
    outcome: str
    amount: int
    fee_bps: int
    claimed: bool
    tx_signature: str | None = None


class SubscriptionInfo(BaseModel):
    wallet: str
    tier: str
    expires_at: datetime
    active: bool


class PayoutPreview(BaseModel):
    outcome: str
    stake: int
    projected_profit: int
    projected_fee: int
    projected_payout: int
    odds: float | None = None


class ClaimPreview(BaseModel):
    match_id: int
    wallet: str
    result: str  # "won" / "lost" / "refund" / "pending"
    payout: int  # amount receivable now (0 for a losing/pending bet)
    fee: int


class CreateMarketRequest(BaseModel):
    match_id: int
    betting_close_ts: datetime | None = None  # defaults to the match kickoff time


class RecordBetRequest(BaseModel):
    match_id: int
    wallet: str
    outcome: str  # HOME / AWAY
    amount: int  # base units
    fee_bps: int | None = None  # defaults to Standard-tier fee
    tx_signature: str | None = None


class RecordSubscriptionRequest(BaseModel):
    wallet: str
    tier: str  # STANDARD / PREMIUM
    expires_at: datetime
