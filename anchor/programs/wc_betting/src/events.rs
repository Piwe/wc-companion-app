use anchor_lang::prelude::*;

use crate::state::{Outcome, SubTier};

#[event]
pub struct MarketCreated {
    pub match_id: u64,
    pub betting_close_ts: i64,
}

#[event]
pub struct BetPlaced {
    pub match_id: u64,
    pub bettor: Pubkey,
    pub outcome: Outcome,
    pub amount: u64,
    pub new_pool_home: u64,
    pub new_pool_away: u64,
}

#[event]
pub struct MarketSettled {
    pub match_id: u64,
    pub outcome: Outcome,
}

#[event]
pub struct MarketVoided {
    pub match_id: u64,
}

#[event]
pub struct Claimed {
    pub match_id: u64,
    pub bettor: Pubkey,
    pub payout: u64,
    pub fee: u64,
    pub refunded: bool,
}

#[event]
pub struct Subscribed {
    pub subscriber: Pubkey,
    pub tier: SubTier,
    pub expires_at: i64,
}
