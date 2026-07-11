//! wc_betting — parimutuel match-winner betting + tiered subscriptions on Solana.
//!
//! See ../../betting-program-spec.md for the full specification. Money model:
//! parimutuel (HOME/AWAY only; a DRAW result voids the market and refunds everyone),
//! USDC (SPL, 6 decimals), fee charged on profit per-bettor at a snapshotted rate.
//!
//! NOTE: the program id below is a placeholder. Run `anchor keys sync` after
//! `anchor build` to replace it with the real deployed id.

use anchor_lang::prelude::*;
use anchor_spl::token::{
    self, CloseAccount, Mint, Token, TokenAccount, Transfer,
};

mod error;
mod events;
mod state;

use error::BettingError;
use events::*;
use state::*;

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

const BPS_DENOMINATOR: u128 = 10_000;
/// How long after betting closes before an admin may sweep + close a market.
const CLOSE_GRACE_SECONDS: i64 = 30 * 24 * 60 * 60;

#[program]
pub mod wc_betting {
    use super::*;

    pub fn initialize_config(
        ctx: Context<InitializeConfig>,
        oracle_authority: Pubkey,
        standard_fee_bps: u16,
        premium_fee_bps: u16,
        standard_price: u64,
        premium_price: u64,
        subscription_duration: i64,
        min_bet: u64,
    ) -> Result<()> {
        require!(
            (standard_fee_bps as u128) <= BPS_DENOMINATOR
                && (premium_fee_bps as u128) <= BPS_DENOMINATOR,
            BettingError::InvalidFeeBps
        );
        let c = &mut ctx.accounts.config;
        c.admin = ctx.accounts.admin.key();
        c.oracle_authority = oracle_authority;
        c.usdc_mint = ctx.accounts.usdc_mint.key();
        c.treasury_ata = ctx.accounts.treasury_ata.key();
        c.standard_fee_bps = standard_fee_bps;
        c.premium_fee_bps = premium_fee_bps;
        c.standard_price = standard_price;
        c.premium_price = premium_price;
        c.subscription_duration = subscription_duration;
        c.min_bet = min_bet;
        c.paused = false;
        c.bump = ctx.bumps.config;
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    pub fn update_config(
        ctx: Context<UpdateConfig>,
        oracle_authority: Option<Pubkey>,
        standard_fee_bps: Option<u16>,
        premium_fee_bps: Option<u16>,
        standard_price: Option<u64>,
        premium_price: Option<u64>,
        subscription_duration: Option<i64>,
        min_bet: Option<u64>,
        paused: Option<bool>,
    ) -> Result<()> {
        let c = &mut ctx.accounts.config;
        if let Some(v) = oracle_authority {
            c.oracle_authority = v;
        }
        if let Some(v) = standard_fee_bps {
            require!((v as u128) <= BPS_DENOMINATOR, BettingError::InvalidFeeBps);
            c.standard_fee_bps = v;
        }
        if let Some(v) = premium_fee_bps {
            require!((v as u128) <= BPS_DENOMINATOR, BettingError::InvalidFeeBps);
            c.premium_fee_bps = v;
        }
        if let Some(v) = standard_price {
            c.standard_price = v;
        }
        if let Some(v) = premium_price {
            c.premium_price = v;
        }
        if let Some(v) = subscription_duration {
            c.subscription_duration = v;
        }
        if let Some(v) = min_bet {
            c.min_bet = v;
        }
        if let Some(v) = paused {
            c.paused = v;
        }
        Ok(())
    }

    pub fn create_market(
        ctx: Context<CreateMarket>,
        match_id: u64,
        home_team_id: u32,
        away_team_id: u32,
        betting_close_ts: i64,
    ) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        require!(betting_close_ts > now, BettingError::InvalidCloseTime);

        let m = &mut ctx.accounts.market;
        m.match_id = match_id;
        m.home_team_id = home_team_id;
        m.away_team_id = away_team_id;
        m.betting_close_ts = betting_close_ts;
        m.status = MarketStatus::Open;
        m.outcome = None;
        m.pool_home = 0;
        m.pool_away = 0;
        m.bet_count = 0;
        m.fees_collected = 0;
        m.vault = ctx.accounts.vault.key();
        m.bump = ctx.bumps.market;
        m.vault_bump = ctx.bumps.vault;

        emit!(MarketCreated { match_id, betting_close_ts });
        Ok(())
    }

    pub fn subscribe(ctx: Context<Subscribe>, tier: SubTier) -> Result<()> {
        let c = &ctx.accounts.config;
        require!(!c.paused, BettingError::Paused);
        let price = match tier {
            SubTier::Standard => c.standard_price,
            SubTier::Premium => c.premium_price,
        };

        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.subscriber_ata.to_account_info(),
                    to: ctx.accounts.treasury_ata.to_account_info(),
                    authority: ctx.accounts.subscriber.to_account_info(),
                },
            ),
            price,
        )?;

        let now = Clock::get()?.unix_timestamp;
        let s = &mut ctx.accounts.subscription;
        // Renewals stack from the later of now / current expiry; upgrades take the new tier now.
        let base = if s.subscriber == Pubkey::default() {
            now
        } else {
            s.expires_at.max(now)
        };
        s.subscriber = ctx.accounts.subscriber.key();
        s.tier = tier;
        s.expires_at = base
            .checked_add(c.subscription_duration)
            .ok_or(BettingError::MathOverflow)?;
        s.bump = ctx.bumps.subscription;

        emit!(Subscribed {
            subscriber: s.subscriber,
            tier: s.tier,
            expires_at: s.expires_at,
        });
        Ok(())
    }

    pub fn place_bet(ctx: Context<PlaceBet>, outcome: Outcome, amount: u64) -> Result<()> {
        let c = &ctx.accounts.config;
        require!(!c.paused, BettingError::Paused);

        let now = Clock::get()?.unix_timestamp;
        let market = &mut ctx.accounts.market;
        require!(market.status == MarketStatus::Open, BettingError::MarketNotOpen);
        require!(now < market.betting_close_ts, BettingError::BettingClosed);
        require!(amount >= c.min_bet, BettingError::BelowMinBet);

        // Bet gate: an active subscription of any tier is required.
        let sub = &ctx.accounts.subscription;
        require!(
            sub.subscriber == ctx.accounts.bettor.key() && now < sub.expires_at,
            BettingError::NotSubscribed
        );

        // Pull the stake into the market vault.
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.bettor_ata.to_account_info(),
                    to: ctx.accounts.vault.to_account_info(),
                    authority: ctx.accounts.bettor.to_account_info(),
                },
            ),
            amount,
        )?;

        let bet = &mut ctx.accounts.bet;
        if bet.amount == 0 {
            // First placement: snapshot side + fee tier.
            bet.market = market.key();
            bet.bettor = ctx.accounts.bettor.key();
            bet.outcome = outcome;
            bet.fee_bps = match sub.tier {
                SubTier::Premium => c.premium_fee_bps,
                SubTier::Standard => c.standard_fee_bps,
            };
            bet.claimed = false;
            bet.bump = ctx.bumps.bet;
            market.bet_count = market.bet_count.checked_add(1).ok_or(BettingError::MathOverflow)?;
        } else {
            // Top-up: must be the same side (no hedging both outcomes).
            require!(bet.outcome == outcome, BettingError::OutcomeMismatch);
        }
        bet.amount = bet.amount.checked_add(amount).ok_or(BettingError::MathOverflow)?;

        match outcome {
            Outcome::Home => {
                market.pool_home =
                    market.pool_home.checked_add(amount).ok_or(BettingError::MathOverflow)?
            }
            Outcome::Away => {
                market.pool_away =
                    market.pool_away.checked_add(amount).ok_or(BettingError::MathOverflow)?
            }
        }

        emit!(BetPlaced {
            match_id: market.match_id,
            bettor: bet.bettor,
            outcome,
            amount,
            new_pool_home: market.pool_home,
            new_pool_away: market.pool_away,
        });
        Ok(())
    }

    pub fn settle_market(ctx: Context<OracleMarket>, outcome: Outcome) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let m = &mut ctx.accounts.market;
        require!(m.status == MarketStatus::Open, BettingError::MarketNotOpen);
        require!(now >= m.betting_close_ts, BettingError::SettleTooEarly);

        let winning_pool = match outcome {
            Outcome::Home => m.pool_home,
            Outcome::Away => m.pool_away,
        };
        if winning_pool == 0 {
            // No winners to distribute to -> void & refund everyone (spec §6.4).
            m.status = MarketStatus::Voided;
            m.outcome = None;
            emit!(MarketVoided { match_id: m.match_id });
        } else {
            m.status = MarketStatus::Settled;
            m.outcome = Some(outcome);
            emit!(MarketSettled { match_id: m.match_id, outcome });
        }
        Ok(())
    }

    pub fn void_market(ctx: Context<OracleMarket>) -> Result<()> {
        let m = &mut ctx.accounts.market;
        require!(m.status == MarketStatus::Open, BettingError::MarketNotOpen);
        m.status = MarketStatus::Voided;
        m.outcome = None;
        emit!(MarketVoided { match_id: m.match_id });
        Ok(())
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        let bet = &mut ctx.accounts.bet;
        require!(!bet.claimed, BettingError::AlreadyClaimed);

        let market = &ctx.accounts.market;
        require!(
            market.status != MarketStatus::Open,
            BettingError::MarketNotResolved
        );

        let (payout, fee, refunded) = if market.status == MarketStatus::Voided {
            (bet.amount, 0u64, true)
        } else if Some(bet.outcome) == market.outcome {
            let (winning, losing) = match bet.outcome {
                Outcome::Home => (market.pool_home, market.pool_away),
                Outcome::Away => (market.pool_away, market.pool_home),
            };
            let (payout, fee) = parimutuel_payout(bet.amount, winning, losing, bet.fee_bps)?;
            (payout, fee, false)
        } else {
            // Losing bet: nothing to transfer, just mark claimed.
            (0u64, 0u64, false)
        };

        bet.claimed = true;

        if payout > 0 || fee > 0 {
            let match_id = market.match_id.to_le_bytes();
            let seeds: &[&[u8]] = &[b"market", match_id.as_ref(), &[market.bump]];
            let signer: &[&[&[u8]]] = &[seeds];

            if payout > 0 {
                token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.vault.to_account_info(),
                            to: ctx.accounts.bettor_ata.to_account_info(),
                            authority: ctx.accounts.market.to_account_info(),
                        },
                        signer,
                    ),
                    payout,
                )?;
            }
            if fee > 0 {
                token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.vault.to_account_info(),
                            to: ctx.accounts.treasury_ata.to_account_info(),
                            authority: ctx.accounts.market.to_account_info(),
                        },
                        signer,
                    ),
                    fee,
                )?;
            }
        }

        emit!(Claimed {
            match_id: market.match_id,
            bettor: bet.bettor,
            payout,
            fee,
            refunded,
        });
        Ok(())
    }

    pub fn close_market(ctx: Context<CloseMarket>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let market = &ctx.accounts.market;
        require!(market.status != MarketStatus::Open, BettingError::MarketNotResolved);
        require!(
            now >= market.betting_close_ts + CLOSE_GRACE_SECONDS,
            BettingError::GracePeriodActive
        );

        let match_id = market.match_id.to_le_bytes();
        let seeds: &[&[u8]] = &[b"market", match_id.as_ref(), &[market.bump]];
        let signer: &[&[&[u8]]] = &[seeds];

        // Sweep any rounding dust to the treasury, then close the vault.
        let dust = ctx.accounts.vault.amount;
        if dust > 0 {
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.to_account_info(),
                    Transfer {
                        from: ctx.accounts.vault.to_account_info(),
                        to: ctx.accounts.treasury_ata.to_account_info(),
                        authority: ctx.accounts.market.to_account_info(),
                    },
                    signer,
                ),
                dust,
            )?;
        }
        token::close_account(CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            CloseAccount {
                account: ctx.accounts.vault.to_account_info(),
                destination: ctx.accounts.admin.to_account_info(),
                authority: ctx.accounts.market.to_account_info(),
            },
            signer,
        ))?;
        // The `market` account is closed via the `close = admin` constraint.
        Ok(())
    }
}

/// Parimutuel payout for a winning bet (spec §6). Returns (payout, fee).
fn parimutuel_payout(stake: u64, winning: u64, losing: u64, fee_bps: u16) -> Result<(u64, u64)> {
    if winning == 0 {
        return Ok((stake, 0));
    }
    let profit = (stake as u128)
        .checked_mul(losing as u128)
        .ok_or(BettingError::MathOverflow)?
        .checked_div(winning as u128)
        .ok_or(BettingError::MathOverflow)?;
    let fee = profit
        .checked_mul(fee_bps as u128)
        .ok_or(BettingError::MathOverflow)?
        / BPS_DENOMINATOR;
    let payout = (stake as u128)
        .checked_add(profit)
        .ok_or(BettingError::MathOverflow)?
        .checked_sub(fee)
        .ok_or(BettingError::MathOverflow)?;
    Ok((
        u64::try_from(payout).map_err(|_| BettingError::MathOverflow)?,
        u64::try_from(fee).map_err(|_| BettingError::MathOverflow)?,
    ))
}

// --- Account contexts --------------------------------------------------------

#[derive(Accounts)]
pub struct InitializeConfig<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        init,
        payer = admin,
        space = 8 + Config::INIT_SPACE,
        seeds = [b"config"],
        bump
    )]
    pub config: Account<'info, Config>,
    pub usdc_mint: Account<'info, Mint>,
    #[account(constraint = treasury_ata.mint == usdc_mint.key() @ BettingError::InvalidMint)]
    pub treasury_ata: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    pub admin: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump, has_one = admin @ BettingError::Unauthorized)]
    pub config: Account<'info, Config>,
}

#[derive(Accounts)]
#[instruction(match_id: u64)]
pub struct CreateMarket<'info> {
    #[account(mut)]
    pub oracle_authority: Signer<'info>,
    #[account(
        seeds = [b"config"],
        bump = config.bump,
        constraint = config.oracle_authority == oracle_authority.key() @ BettingError::Unauthorized
    )]
    pub config: Account<'info, Config>,
    #[account(
        init,
        payer = oracle_authority,
        space = 8 + Market::INIT_SPACE,
        seeds = [b"market", match_id.to_le_bytes().as_ref()],
        bump
    )]
    pub market: Account<'info, Market>,
    #[account(
        init,
        payer = oracle_authority,
        seeds = [b"vault", market.key().as_ref()],
        bump,
        token::mint = usdc_mint,
        token::authority = market
    )]
    pub vault: Account<'info, TokenAccount>,
    #[account(address = config.usdc_mint @ BettingError::InvalidMint)]
    pub usdc_mint: Account<'info, Mint>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Subscribe<'info> {
    #[account(mut)]
    pub subscriber: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    #[account(
        init_if_needed,
        payer = subscriber,
        space = 8 + Subscription::INIT_SPACE,
        seeds = [b"subscription", subscriber.key().as_ref()],
        bump
    )]
    pub subscription: Account<'info, Subscription>,
    #[account(mut, constraint = subscriber_ata.mint == config.usdc_mint @ BettingError::InvalidMint)]
    pub subscriber_ata: Account<'info, TokenAccount>,
    #[account(mut, address = config.treasury_ata @ BettingError::InvalidTreasury)]
    pub treasury_ata: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct PlaceBet<'info> {
    #[account(mut)]
    pub bettor: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    #[account(mut, seeds = [b"market", market.match_id.to_le_bytes().as_ref()], bump = market.bump)]
    pub market: Account<'info, Market>,
    #[account(
        init_if_needed,
        payer = bettor,
        space = 8 + Bet::INIT_SPACE,
        seeds = [b"bet", market.key().as_ref(), bettor.key().as_ref()],
        bump
    )]
    pub bet: Account<'info, Bet>,
    #[account(seeds = [b"subscription", bettor.key().as_ref()], bump = subscription.bump)]
    pub subscription: Account<'info, Subscription>,
    #[account(mut, constraint = bettor_ata.mint == config.usdc_mint @ BettingError::InvalidMint)]
    pub bettor_ata: Account<'info, TokenAccount>,
    #[account(mut, address = market.vault)]
    pub vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct OracleMarket<'info> {
    #[account(
        seeds = [b"config"],
        bump = config.bump,
        constraint = config.oracle_authority == oracle_authority.key() @ BettingError::Unauthorized
    )]
    pub config: Account<'info, Config>,
    pub oracle_authority: Signer<'info>,
    #[account(mut, seeds = [b"market", market.match_id.to_le_bytes().as_ref()], bump = market.bump)]
    pub market: Account<'info, Market>,
}

#[derive(Accounts)]
pub struct Claim<'info> {
    #[account(mut)]
    pub bettor: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    #[account(seeds = [b"market", market.match_id.to_le_bytes().as_ref()], bump = market.bump)]
    pub market: Account<'info, Market>,
    #[account(
        mut,
        seeds = [b"bet", market.key().as_ref(), bettor.key().as_ref()],
        bump = bet.bump,
        has_one = bettor @ BettingError::Unauthorized,
        constraint = bet.market == market.key() @ BettingError::Unauthorized,
        close = bettor
    )]
    pub bet: Account<'info, Bet>,
    #[account(mut, address = market.vault)]
    pub vault: Account<'info, TokenAccount>,
    #[account(mut, constraint = bettor_ata.mint == config.usdc_mint @ BettingError::InvalidMint)]
    pub bettor_ata: Account<'info, TokenAccount>,
    #[account(mut, address = config.treasury_ata @ BettingError::InvalidTreasury)]
    pub treasury_ata: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct CloseMarket<'info> {
    #[account(mut, address = config.admin @ BettingError::Unauthorized)]
    pub admin: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    #[account(
        mut,
        seeds = [b"market", market.match_id.to_le_bytes().as_ref()],
        bump = market.bump,
        close = admin
    )]
    pub market: Account<'info, Market>,
    #[account(mut, address = market.vault)]
    pub vault: Account<'info, TokenAccount>,
    #[account(mut, address = config.treasury_ata @ BettingError::InvalidTreasury)]
    pub treasury_ata: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}
