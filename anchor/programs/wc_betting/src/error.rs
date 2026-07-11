use anchor_lang::prelude::*;

#[error_code]
pub enum BettingError {
    #[msg("Fee basis points must be <= 10000")]
    InvalidFeeBps,
    #[msg("Caller is not authorized for this action")]
    Unauthorized,
    #[msg("Program is paused")]
    Paused,
    #[msg("Market is not open")]
    MarketNotOpen,
    #[msg("Betting has closed for this market")]
    BettingClosed,
    #[msg("Cannot settle before betting closes")]
    SettleTooEarly,
    #[msg("Stake is below the minimum bet")]
    BelowMinBet,
    #[msg("An active subscription is required to place a bet")]
    NotSubscribed,
    #[msg("Wallet already has a bet on the other outcome")]
    OutcomeMismatch,
    #[msg("Bet has already been claimed")]
    AlreadyClaimed,
    #[msg("Market has not been resolved yet")]
    MarketNotResolved,
    #[msg("Token account mint does not match the configured USDC mint")]
    InvalidMint,
    #[msg("Treasury token account does not match config")]
    InvalidTreasury,
    #[msg("Arithmetic overflow")]
    MathOverflow,
    #[msg("Close grace period has not elapsed")]
    GracePeriodActive,
    #[msg("betting_close_ts must be in the future")]
    InvalidCloseTime,
}
