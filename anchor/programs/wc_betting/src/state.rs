use anchor_lang::prelude::*;

/// Global singleton. Seeds: [b"config"].
#[account]
#[derive(InitSpace)]
pub struct Config {
    pub admin: Pubkey,
    pub oracle_authority: Pubkey, // only signer allowed to settle/void (Squads multisig)
    pub usdc_mint: Pubkey,
    pub treasury_ata: Pubkey, // receives fees + subscription revenue
    pub standard_fee_bps: u16,
    pub premium_fee_bps: u16,
    pub standard_price: u64,
    pub premium_price: u64,
    pub subscription_duration: i64, // seconds
    pub min_bet: u64,
    pub paused: bool,
    pub bump: u8,
}

/// One per match. Seeds: [b"market", match_id.to_le_bytes()].
#[account]
#[derive(InitSpace)]
pub struct Market {
    pub match_id: u64,
    pub home_team_id: u32,
    pub away_team_id: u32,
    pub betting_close_ts: i64,
    pub status: MarketStatus,
    pub outcome: Option<Outcome>,
    pub pool_home: u64,
    pub pool_away: u64,
    pub bet_count: u32,
    pub fees_collected: u64,
    pub vault: Pubkey,
    pub bump: u8,
    pub vault_bump: u8,
}

/// One per (market, bettor). Seeds: [b"bet", market, bettor]. Additive, single side.
#[account]
#[derive(InitSpace)]
pub struct Bet {
    pub market: Pubkey,
    pub bettor: Pubkey,
    pub outcome: Outcome,
    pub amount: u64,
    pub fee_bps: u16, // snapshotted at first placement
    pub claimed: bool,
    pub bump: u8,
}

/// One per wallet. Seeds: [b"subscription", subscriber].
#[account]
#[derive(InitSpace)]
pub struct Subscription {
    pub subscriber: Pubkey,
    pub tier: SubTier,
    pub expires_at: i64,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace, Debug)]
pub enum Outcome {
    Home,
    Away,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace, Debug)]
pub enum MarketStatus {
    Open,
    Settled,
    Voided,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace, Debug)]
pub enum SubTier {
    Standard,
    Premium,
}
