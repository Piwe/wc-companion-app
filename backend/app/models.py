from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
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


# --- Betting layer -----------------------------------------------------------
# These tables mirror on-chain state from the wc_betting Anchor program
# (see betting-program-spec.md). The Solana program is the source of truth for
# funds; the backend indexes it here so the UI can read SQLite instead of RPC.

MARKET_OPEN = "OPEN"
MARKET_SETTLED = "SETTLED"
MARKET_VOIDED = "VOIDED"

OUTCOME_HOME = "HOME"
OUTCOME_AWAY = "AWAY"

TIER_STANDARD = "STANDARD"
TIER_PREMIUM = "PREMIUM"


class BettingMarket(Base):
    """Mirror of an on-chain Market PDA (one per match)."""

    __tablename__ = "betting_markets"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True, default=MARKET_OPEN)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)  # HOME / AWAY
    betting_close_ts: Mapped[datetime | None] = mapped_column(nullable=True)
    pool_home: Mapped[int] = mapped_column(default=0)  # USDC base units
    pool_away: Mapped[int] = mapped_column(default=0)
    bet_count: Mapped[int] = mapped_column(default=0)
    market_pubkey: Mapped[str | None] = mapped_column(String, nullable=True)  # on-chain PDA

    match: Mapped[Match] = relationship("Match")


class BetRecord(Base):
    """Mirror of an on-chain Bet PDA (one per market per wallet, additive, single side)."""

    __tablename__ = "betting_bets"
    __table_args__ = (UniqueConstraint("match_id", "wallet", name="uq_bet_market_wallet"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("betting_markets.match_id"), index=True)
    wallet: Mapped[str] = mapped_column(String, index=True)  # bettor pubkey
    outcome: Mapped[str] = mapped_column(String)  # HOME / AWAY
    amount: Mapped[int] = mapped_column(default=0)  # total staked, base units
    fee_bps: Mapped[int] = mapped_column()  # snapshotted at first placement
    claimed: Mapped[bool] = mapped_column(default=False)
    tx_signature: Mapped[str | None] = mapped_column(String, nullable=True)


class Subscription(Base):
    """Mirror of an on-chain Subscription PDA (one per wallet)."""

    __tablename__ = "betting_subscriptions"

    wallet: Mapped[str] = mapped_column(String, primary_key=True)
    tier: Mapped[str] = mapped_column(String)  # STANDARD / PREMIUM
    expires_at: Mapped[datetime] = mapped_column()
