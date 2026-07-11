"""Analytics event emission — the append-only landing zone for the warehouse.

Design goals (see analytics-schema.md):
- **Immutable & append-only.** Never update/delete; corrections are new events.
- **Transactional.** ``emit`` flushes within the caller's transaction so the event and
  the mirror-table change commit atomically (or roll back together).
- **Warehouse-friendly.** Money is stored as integer USDC base units (exact), timestamps
  are naive UTC, the payload is canonical JSON (→ Snowflake VARIANT), and ``event_id`` is
  monotonic so ELT can extract incrementally with a simple ``event_id > watermark``.
- **Idempotent.** A repeated ``dedupe_key`` (e.g. an indexer replaying an on-chain log)
  returns the existing row instead of inserting a duplicate.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalyticsEvent

# Bump when the payload contract changes; carried on every row so the warehouse can
# branch on it during modeling.
SCHEMA_VERSION = 1

# Event catalogue.
MARKET_CREATED = "MARKET_CREATED"
BET_PLACED = "BET_PLACED"
MARKET_SETTLED = "MARKET_SETTLED"
MARKET_VOIDED = "MARKET_VOIDED"
BET_CLAIMED = "BET_CLAIMED"
SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def emit(
    db: Session,
    event_type: str,
    payload: dict,
    *,
    occurred_at: datetime | None = None,
    match_id: int | None = None,
    wallet: str | None = None,
    tx_signature: str | None = None,
    dedupe_key: str | None = None,
) -> AnalyticsEvent:
    """Append one event. Caller is responsible for committing the surrounding transaction."""
    if dedupe_key is not None:
        existing = db.scalar(select(AnalyticsEvent).where(AnalyticsEvent.dedupe_key == dedupe_key))
        if existing is not None:
            return existing

    event = AnalyticsEvent(
        event_type=event_type,
        occurred_at=occurred_at or utcnow(),
        ingested_at=utcnow(),
        schema_version=SCHEMA_VERSION,
        match_id=match_id,
        wallet=wallet,
        tx_signature=tx_signature,
        dedupe_key=dedupe_key,
        # sort_keys + compact separators => stable, diff-friendly, compact JSON.
        payload=json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str),
    )
    db.add(event)
    db.flush()  # assign event_id without ending the caller's transaction
    return event
