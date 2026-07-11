"""Betting endpoints.

Read APIs serve the mirror tables (markets/bets/subscriptions) with live parimutuel
odds. The ``/admin`` endpoints mirror the privileged on-chain instructions
(create_market / settle_market / and the indexer's record-bet & record-subscription
upserts). In production the record-* endpoints are replaced by a chain event listener;
they exist now so the layer is exercisable without a deployed program.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import analytics, betting, schemas, serializers
from app.config import get_settings
from app.database import get_db
from app.models import (
    MARKET_OPEN,
    MARKET_SETTLED,
    MARKET_VOIDED,
    OUTCOME_AWAY,
    OUTCOME_HOME,
    AnalyticsEvent,
    BetRecord,
    BettingMarket,
    Match,
    Subscription,
)

router = APIRouter(prefix="/api/betting", tags=["betting"])

_OUTCOMES = {OUTCOME_HOME, OUTCOME_AWAY}
# Football-Data winner value -> our outcome (spec §5 oracle mapping).
_WINNER_TO_OUTCOME = {"HOME_TEAM": OUTCOME_HOME, "AWAY_TEAM": OUTCOME_AWAY}


def _now() -> datetime:
    # Stored datetimes are naive UTC (SQLite), so compare against a naive-UTC "now".
    return datetime.now(timezone.utc).replace(tzinfo=None)


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if x_admin_token != get_settings().admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _get_market(db: Session, match_id: int) -> BettingMarket:
    market = db.get(BettingMarket, match_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


# --- Public reads ------------------------------------------------------------


@router.get("/markets", response_model=list[schemas.MarketSummary])
def list_markets(
    status: str | None = Query(default=None, description="Filter by OPEN/SETTLED/VOIDED"),
    db: Session = Depends(get_db),
):
    stmt = select(BettingMarket)
    if status is not None:
        stmt = stmt.where(BettingMarket.status == status.upper())
    markets = db.scalars(stmt).all()
    return [serializers.market_summary(m) for m in markets]


@router.get("/markets/{match_id}", response_model=schemas.MarketSummary)
def get_market(match_id: int, db: Session = Depends(get_db)):
    return serializers.market_summary(_get_market(db, match_id))


@router.get("/markets/{match_id}/preview", response_model=schemas.PayoutPreview)
def preview_bet(
    match_id: int,
    outcome: str = Query(..., description="HOME or AWAY"),
    amount: int = Query(..., gt=0, description="Stake in USDC base units"),
    tier: str = Query(default="STANDARD", description="STANDARD or PREMIUM (fee tier)"),
    db: Session = Depends(get_db),
):
    outcome = outcome.upper()
    if outcome not in _OUTCOMES:
        raise HTTPException(status_code=422, detail="outcome must be HOME or AWAY")
    market = _get_market(db, match_id)
    settings = get_settings()
    fee_bps = settings.premium_fee_bps if tier.upper() == "PREMIUM" else settings.standard_fee_bps

    side_pool = market.pool_home if outcome == OUTCOME_HOME else market.pool_away
    other_pool = market.pool_away if outcome == OUTCOME_HOME else market.pool_home
    p = betting.preview_payout(amount, side_pool, other_pool, fee_bps)
    return schemas.PayoutPreview(
        outcome=outcome,
        stake=p.stake,
        projected_profit=p.profit,
        projected_fee=p.fee,
        projected_payout=p.payout,
        odds=betting.gross_decimal_odds(side_pool + amount, other_pool),
    )


@router.get("/wallets/{wallet}/bets", response_model=list[schemas.BetSummary])
def wallet_bets(wallet: str, db: Session = Depends(get_db)):
    bets = db.scalars(select(BetRecord).where(BetRecord.wallet == wallet)).all()
    return [serializers.bet_summary(b) for b in bets]


@router.get("/wallets/{wallet}/subscription", response_model=schemas.SubscriptionInfo)
def wallet_subscription(wallet: str, db: Session = Depends(get_db)):
    sub = db.get(Subscription, wallet)
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription for wallet")
    return serializers.subscription_info(sub, _now())


@router.get("/markets/{match_id}/claim/{wallet}", response_model=schemas.ClaimPreview)
def claim_preview(match_id: int, wallet: str, db: Session = Depends(get_db)):
    """What ``wallet`` can claim on this market given its current settlement state."""
    market = _get_market(db, match_id)
    bet = db.scalar(
        select(BetRecord).where(BetRecord.match_id == match_id, BetRecord.wallet == wallet)
    )
    if bet is None:
        raise HTTPException(status_code=404, detail="No bet for wallet on this market")

    if market.status == MARKET_OPEN:
        return schemas.ClaimPreview(match_id=match_id, wallet=wallet, result="pending", payout=0, fee=0)
    if market.status == MARKET_VOIDED:
        return schemas.ClaimPreview(
            match_id=match_id, wallet=wallet, result="refund", payout=bet.amount, fee=0
        )
    # SETTLED
    if bet.outcome != market.outcome:
        return schemas.ClaimPreview(match_id=match_id, wallet=wallet, result="lost", payout=0, fee=0)
    winning_pool = market.pool_home if market.outcome == OUTCOME_HOME else market.pool_away
    losing_pool = market.pool_away if market.outcome == OUTCOME_HOME else market.pool_home
    p = betting.settle_payout(bet.amount, winning_pool, losing_pool, bet.fee_bps)
    return schemas.ClaimPreview(
        match_id=match_id, wallet=wallet, result="won", payout=p.payout, fee=p.fee
    )


# --- Admin / oracle / indexer ------------------------------------------------


class SettleMarketRequest(BaseModel):
    void: bool = False  # force a void (draw / cancellation)
    outcome: str | None = None  # override; otherwise derived from the match result


@router.post(
    "/admin/markets", response_model=schemas.MarketSummary, dependencies=[Depends(require_admin)]
)
def create_market(req: schemas.CreateMarketRequest, db: Session = Depends(get_db)):
    match = db.get(Match, req.match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if db.get(BettingMarket, req.match_id) is not None:
        raise HTTPException(status_code=409, detail="Market already exists for this match")

    close_ts = req.betting_close_ts or match.utc_date
    if close_ts is not None and close_ts.tzinfo is not None:
        close_ts = close_ts.astimezone(timezone.utc).replace(tzinfo=None)

    market = BettingMarket(match_id=req.match_id, status=MARKET_OPEN, betting_close_ts=close_ts)
    db.add(market)
    analytics.emit(
        db,
        analytics.MARKET_CREATED,
        {
            "match_id": req.match_id,
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "betting_close_ts": close_ts.isoformat() if close_ts else None,
        },
        match_id=req.match_id,
        dedupe_key=f"{analytics.MARKET_CREATED}:{req.match_id}",
    )
    db.commit()
    db.refresh(market)
    return serializers.market_summary(market)


@router.post(
    "/admin/markets/{match_id}/settle",
    response_model=schemas.MarketSummary,
    dependencies=[Depends(require_admin)],
)
def settle_market(match_id: int, req: SettleMarketRequest, db: Session = Depends(get_db)):
    market = _get_market(db, match_id)
    if market.status != MARKET_OPEN:
        raise HTTPException(status_code=409, detail=f"Market is already {market.status}")

    # Resolve the winning outcome, or decide to void.
    outcome: str | None = None
    if not req.void:
        if req.outcome is not None:
            outcome = req.outcome.upper()
            if outcome not in _OUTCOMES:
                raise HTTPException(status_code=422, detail="outcome must be HOME or AWAY")
        else:
            match = db.get(Match, match_id)
            if match is None or match.status != "FINISHED" or match.winner is None:
                raise HTTPException(status_code=409, detail="Match not finished; cannot settle")
            # DRAW (or any non-team winner) -> void & refund (spec §5).
            outcome = _WINNER_TO_OUTCOME.get(match.winner)

    if outcome is not None:
        # Empty-winning-pool guard (spec §6.4): nobody to pay -> void & refund everyone.
        winning_pool = market.pool_home if outcome == OUTCOME_HOME else market.pool_away
        if winning_pool == 0:
            outcome = None

    if outcome is None:
        market.status = MARKET_VOIDED
        market.outcome = None
        analytics.emit(
            db,
            analytics.MARKET_VOIDED,
            {
                "match_id": match_id,
                "pool_home": market.pool_home,
                "pool_away": market.pool_away,
                "total_pool": market.pool_home + market.pool_away,
            },
            match_id=match_id,
            dedupe_key=f"{analytics.MARKET_VOIDED}:{match_id}",
        )
    else:
        market.status = MARKET_SETTLED
        market.outcome = outcome
        winning_pool = market.pool_home if outcome == OUTCOME_HOME else market.pool_away
        analytics.emit(
            db,
            analytics.MARKET_SETTLED,
            {
                "match_id": match_id,
                "outcome": outcome,
                "pool_home": market.pool_home,
                "pool_away": market.pool_away,
                "total_pool": market.pool_home + market.pool_away,
                "winning_pool": winning_pool,
            },
            match_id=match_id,
            dedupe_key=f"{analytics.MARKET_SETTLED}:{match_id}",
        )

    db.commit()
    db.refresh(market)
    return serializers.market_summary(market)


@router.post(
    "/admin/bets", response_model=schemas.BetSummary, dependencies=[Depends(require_admin)]
)
def record_bet(req: schemas.RecordBetRequest, db: Session = Depends(get_db)):
    """Record an on-chain BetPlaced event into the mirror (indexer ingestion)."""
    outcome = req.outcome.upper()
    if outcome not in _OUTCOMES:
        raise HTTPException(status_code=422, detail="outcome must be HOME or AWAY")
    if req.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive")

    market = _get_market(db, req.match_id)
    if market.status != MARKET_OPEN:
        raise HTTPException(status_code=409, detail=f"Market is {market.status}; bets closed")

    settings = get_settings()
    fee_bps = req.fee_bps if req.fee_bps is not None else settings.standard_fee_bps

    bet = db.scalar(
        select(BetRecord).where(
            BetRecord.match_id == req.match_id, BetRecord.wallet == req.wallet
        )
    )
    if bet is None:
        bet = BetRecord(
            match_id=req.match_id,
            wallet=req.wallet,
            outcome=outcome,
            amount=req.amount,
            fee_bps=fee_bps,
            tx_signature=req.tx_signature,
        )
        db.add(bet)
        market.bet_count += 1
    else:
        # Additive top-up; hedging the opposite side is disallowed (spec D7).
        if bet.outcome != outcome:
            raise HTTPException(status_code=409, detail="Wallet already bet the other side")
        bet.amount += req.amount
        if req.tx_signature:
            bet.tx_signature = req.tx_signature

    if outcome == OUTCOME_HOME:
        market.pool_home += req.amount
    else:
        market.pool_away += req.amount

    analytics.emit(
        db,
        analytics.BET_PLACED,
        {
            "match_id": req.match_id,
            "wallet": req.wallet,
            "outcome": outcome,
            "amount": req.amount,  # this placement only (grain = one placement event)
            "fee_bps": fee_bps,
            "new_pool_home": market.pool_home,
            "new_pool_away": market.pool_away,
        },
        match_id=req.match_id,
        wallet=req.wallet,
        tx_signature=req.tx_signature,
        dedupe_key=f"{analytics.BET_PLACED}:{req.tx_signature}" if req.tx_signature else None,
    )

    db.commit()
    db.refresh(bet)
    return serializers.bet_summary(bet)


@router.post(
    "/admin/subscriptions",
    response_model=schemas.SubscriptionInfo,
    dependencies=[Depends(require_admin)],
)
def record_subscription(req: schemas.RecordSubscriptionRequest, db: Session = Depends(get_db)):
    """Record an on-chain Subscribed event into the mirror (indexer ingestion)."""
    tier = req.tier.upper()
    expires_at = req.expires_at
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)

    sub = db.get(Subscription, req.wallet)
    if sub is None:
        sub = Subscription(wallet=req.wallet, tier=tier, expires_at=expires_at)
        db.add(sub)
    else:
        sub.tier = tier
        sub.expires_at = expires_at
    analytics.emit(
        db,
        analytics.SUBSCRIPTION_CREATED,
        {"wallet": req.wallet, "tier": tier, "expires_at": expires_at.isoformat()},
        wallet=req.wallet,
    )
    db.commit()
    db.refresh(sub)
    return serializers.subscription_info(sub, _now())


@router.post(
    "/admin/claims", response_model=schemas.BetSummary, dependencies=[Depends(require_admin)]
)
def record_claim(req: schemas.RecordClaimRequest, db: Session = Depends(get_db)):
    """Record an on-chain Claimed event into the mirror (indexer ingestion)."""
    market = _get_market(db, req.match_id)
    if market.status == MARKET_OPEN:
        raise HTTPException(status_code=409, detail="Market is not resolved; nothing to claim")

    bet = db.scalar(
        select(BetRecord).where(
            BetRecord.match_id == req.match_id, BetRecord.wallet == req.wallet
        )
    )
    if bet is None:
        raise HTTPException(status_code=404, detail="No bet for wallet on this market")

    bet.claimed = True
    if req.tx_signature:
        bet.tx_signature = req.tx_signature

    analytics.emit(
        db,
        analytics.BET_CLAIMED,
        {
            "match_id": req.match_id,
            "wallet": req.wallet,
            "payout": req.payout,
            "fee": req.fee,
            "refunded": req.refunded,
        },
        match_id=req.match_id,
        wallet=req.wallet,
        tx_signature=req.tx_signature,
        dedupe_key=(
            f"{analytics.BET_CLAIMED}:{req.tx_signature}"
            if req.tx_signature
            else f"{analytics.BET_CLAIMED}:{req.match_id}:{req.wallet}"
        ),
    )
    db.commit()
    db.refresh(bet)
    return serializers.bet_summary(bet)


@router.get(
    "/analytics/events",
    response_model=list[schemas.AnalyticsEventOut],
    dependencies=[Depends(require_admin)],
)
def analytics_events(
    after_id: int = Query(default=0, ge=0, description="Return events with event_id > this"),
    limit: int = Query(default=500, gt=0, le=5000),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Watermark-based extraction feed for the warehouse ELT.

    Poll with the last ``event_id`` you saw as ``after_id`` to pull only new events, in
    order. This is the loader-agnostic interface an ELT job / Fivetran custom connector
    reads to land rows in Snowflake (see analytics-schema.md).
    """
    stmt = select(AnalyticsEvent).where(AnalyticsEvent.event_id > after_id)
    if event_type is not None:
        stmt = stmt.where(AnalyticsEvent.event_type == event_type)
    events = db.scalars(stmt.order_by(AnalyticsEvent.event_id).limit(limit)).all()
    return [serializers.analytics_event(e) for e in events]
