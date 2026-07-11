"""Parimutuel odds & payout math for the betting layer.

Mirrors the on-chain ``wc_betting`` Anchor program (see betting-program-spec.md §6).
All monetary amounts are USDC **base units** (integers, 6 decimals). Division floors,
exactly matching the Rust integer arithmetic so off-chain previews agree with on-chain
settlement to the base unit.
"""

from dataclasses import dataclass

BPS_DENOMINATOR = 10_000


@dataclass(frozen=True)
class Payout:
    """Result of settling one winning bet."""

    stake: int
    profit: int
    fee: int
    payout: int  # stake + profit - fee, i.e. what the bettor receives


def gross_decimal_odds(side_pool: int, other_pool: int) -> float | None:
    """Display (pre-fee) decimal odds for a side: total_pool / side_pool.

    Returns ``None`` when the side has no stake yet (odds undefined).
    """
    if side_pool <= 0:
        return None
    return (side_pool + other_pool) / side_pool


def settle_payout(stake: int, winning_pool: int, losing_pool: int, fee_bps: int) -> Payout:
    """Payout for a winning bet under parimutuel rules (spec §6).

    ``winning_pool`` is the TOTAL stake on the winning side *including* this bet.
    Fee is charged on profit only, at the bettor's snapshotted ``fee_bps``.
    """
    if stake <= 0 or winning_pool <= 0:
        return Payout(stake=max(stake, 0), profit=0, fee=0, payout=max(stake, 0))
    # u128-equivalent intermediate; Python ints are unbounded so overflow is not a concern here.
    profit = stake * losing_pool // winning_pool
    fee = profit * fee_bps // BPS_DENOMINATOR
    return Payout(stake=stake, profit=profit, fee=fee, payout=stake + profit - fee)


def preview_payout(stake: int, side_pool: int, other_pool: int, fee_bps: int) -> Payout:
    """Projected payout *if this stake were placed now and its side won*.

    ``side_pool`` is the chosen side's current pool BEFORE this stake is added.
    """
    return settle_payout(stake, side_pool + stake, other_pool, fee_bps)
