# WC Betting — Anchor Program Specification

**Program name:** `wc_betting`
**Framework:** Anchor (Rust)
**Network:** Solana Devnet (fake USDC) first → mainnet after audit
**Currency:** USDC (SPL token, 6 decimals)
**Betting model:** Parimutuel pool, HOME/AWAY only. A `DRAW` match result voids the market and refunds all stakes.

This document specifies the on-chain program only. The FastAPI backend acts solely as the
**oracle** (pushes results) and **indexer** (mirrors state for the UI); it never custodies funds.

---

## 0. Key design decisions (and why)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Parimutuel**, not fixed-odds | No house bankroll, no odds oracle. Odds emerge from pool sizes. |
| D2 | Offer **HOME / AWAY only**; `DRAW` → **void + full refund** | Matches "bet only on team winnings." No draw pool to manage. |
| D3 | **Fee charged on profit, per-bettor** (not once on the whole pool) | Lets different bettors carry different fee rates without breaking pool accounting (see §6). |
| D4 | **Two subscription tiers** — `Standard` and `Premium` | Reconciles "subscription required to bet" **and** "subscribers get a lower fee." If every bettor must subscribe, a flat subscriber discount is meaningless. `Standard` = the bet gate + premium companion features; `Premium` = adds the reduced fee. |
| D5 | Fee rate is **snapshotted into the `Bet`** at placement time | Deterministic; prevents subscribing-right-before-claim to grab a discount; decouples `claim` from reading the live `Subscription`. |
| D6 | `oracle_authority` = a **Squads multisig**, not a raw backend key | A leaked server key must not be able to settle markets fraudulently. |
| D7 | One `Bet` PDA per `(market, bettor)`, **additive, single side** | Simple unique seed; a user picks a side and can top up. Hedging both sides of the same market is disallowed. |

---

## 1. Accounts (on-chain state)

### 1.1 `Config` — singleton
Seeds: `[b"config"]`

| Field | Type | Notes |
|-------|------|-------|
| `admin` | `Pubkey` | Can update config, pause, close markets. |
| `oracle_authority` | `Pubkey` | Only signer allowed to settle/void markets (Squads multisig). |
| `usdc_mint` | `Pubkey` | The accepted token mint. Every token account is validated against this. |
| `treasury_ata` | `Pubkey` | USDC token account receiving fees + subscription revenue. |
| `standard_fee_bps` | `u16` | House fee on **profit** for `Standard`-tier bettors (e.g. `500` = 5%). |
| `premium_fee_bps` | `u16` | Reduced fee on profit for `Premium`-tier bettors (e.g. `200` = 2%). |
| `standard_price` | `u64` | Subscription price, `Standard` tier (USDC base units). |
| `premium_price` | `u64` | Subscription price, `Premium` tier. |
| `subscription_duration` | `i64` | Seconds a subscription is valid (e.g. 30 days). |
| `min_bet` | `u64` | Minimum stake per `place_bet` call. |
| `paused` | `bool` | Kill switch: blocks `place_bet` and `subscribe`. |
| `bump` | `u8` | PDA bump. |

### 1.2 `Market` — one per match
Seeds: `[b"market", match_id.to_le_bytes()]`

| Field | Type | Notes |
|-------|------|-------|
| `match_id` | `u64` | Football-Data match id (mirrors `Match.id`). |
| `home_team_id` | `u32` | For display/validation. |
| `away_team_id` | `u32` | |
| `betting_close_ts` | `i64` | Unix seconds. No bets accepted at/after this. Set to kickoff time. |
| `status` | `MarketStatus` | `Open` → `Settled` \| `Voided`. |
| `outcome` | `Option<Outcome>` | Set on settle. `None` while Open/Voided. |
| `pool_home` | `u64` | Total staked on HOME. |
| `pool_away` | `u64` | Total staked on AWAY. |
| `bet_count` | `u32` | Number of `Bet` accounts (for indexer/UX). |
| `fees_collected` | `u64` | Cumulative fee routed to treasury from this market's claims. |
| `vault` | `Pubkey` | Program-owned USDC token account holding all stakes. |
| `bump` | `u8` | |
| `vault_bump` | `u8` | |

`vault` authority = the `Market` PDA. Seeds for the vault token account: `[b"vault", market.key()]`.

### 1.3 `Bet` — one per (market, bettor)
Seeds: `[b"bet", market.key(), bettor.key()]`

| Field | Type | Notes |
|-------|------|-------|
| `market` | `Pubkey` | Parent market. |
| `bettor` | `Pubkey` | Owner. |
| `outcome` | `Outcome` | The side chosen (locked after first bet). |
| `amount` | `u64` | Total staked (additive across top-ups). |
| `fee_bps` | `u16` | Snapshot of the bettor's tier fee at first placement (D5). |
| `claimed` | `bool` | Prevents double claim/refund. |
| `bump` | `u8` | |

### 1.4 `Subscription` — one per user
Seeds: `[b"subscription", subscriber.key()]`

| Field | Type | Notes |
|-------|------|-------|
| `subscriber` | `Pubkey` | Owner. |
| `tier` | `SubTier` | `Standard` \| `Premium`. |
| `expires_at` | `i64` | Unix seconds. Active iff `now < expires_at`. |
| `bump` | `u8` | |

### 1.5 Enums

```rust
pub enum Outcome      { Home, Away }
pub enum MarketStatus { Open, Settled, Voided }
pub enum SubTier      { Standard, Premium }
```

### 1.6 Seed reference

| Account | Seeds |
|---------|-------|
| Config | `[b"config"]` |
| Market | `[b"market", match_id.to_le_bytes()]` |
| Vault (token acct) | `[b"vault", market_pubkey]` |
| Bet | `[b"bet", market_pubkey, bettor_pubkey]` |
| Subscription | `[b"subscription", subscriber_pubkey]` |

---

## 2. Instruction summary

| # | Instruction | Signer | Purpose |
|---|-------------|--------|---------|
| 1 | `initialize_config` | admin | One-time setup of `Config`. |
| 2 | `update_config` | admin | Tune fees, prices, pause. |
| 3 | `create_market` | oracle_authority | Open a market for a match. |
| 4 | `subscribe` | user | Pay for / renew a subscription tier. |
| 5 | `place_bet` | user | Stake USDC on HOME or AWAY. |
| 6 | `settle_market` | oracle_authority | Record the winning side. |
| 7 | `void_market` | oracle_authority | Void (draw, cancellation, or empty winning pool). |
| 8 | `claim` | user | Collect winnings, or refund if voided. |
| 9 | `close_market` | admin | Sweep rounding dust to treasury + reclaim rent after full settlement. |

---

## 3. Instruction details

### 3.1 `initialize_config`
**Args:** `oracle_authority`, `usdc_mint`, `standard_fee_bps`, `premium_fee_bps`, `standard_price`, `premium_price`, `subscription_duration`, `min_bet`.
**Accounts:** `admin` (signer, payer), `config` (init, PDA), `treasury_ata` (USDC ATA, mint == usdc_mint), `system_program`, `token_program`.
**Checks:** `config` not already initialized; `*_fee_bps <= 10_000`; `treasury_ata.mint == usdc_mint`.
**Effects:** Populate `Config`, store `admin = signer`, `paused = false`.

### 3.2 `update_config`
**Args:** optional overrides for any tunable field + `paused`.
**Accounts:** `admin` (signer), `config` (mut, `has_one = admin`).
**Checks:** signer is `config.admin`; fee bps ≤ 10_000.
**Effects:** Apply provided fields. (Does not touch existing markets/bets.)

### 3.3 `create_market`
**Args:** `match_id: u64`, `home_team_id: u32`, `away_team_id: u32`, `betting_close_ts: i64`.
**Accounts:** `oracle_authority` (signer, `config.oracle_authority`), `config`, `market` (init, PDA by `match_id`), `vault` (init, token acct, authority = market PDA, mint = `config.usdc_mint`), `system_program`, `token_program`, `rent`.
**Checks:** signer == `config.oracle_authority`; `betting_close_ts > now`; market for `match_id` not already created.
**Effects:** `status = Open`, pools = 0, `outcome = None`. Emits `MarketCreated`.

### 3.4 `subscribe`
**Args:** `tier: SubTier`.
**Accounts:** `subscriber` (signer, payer), `config`, `subscription` (init_if_needed, PDA), `subscriber_ata` (mut, mint == usdc_mint), `treasury_ata` (mut, == `config.treasury_ata`), `token_program`, `system_program`.
**Checks:** `!config.paused`; price = `standard_price`/`premium_price` per tier; `subscriber_ata` balance ≥ price.
**Effects:**
- Transfer `price` USDC → `treasury_ata`.
- `tier = tier`.
- Extend validity: `expires_at = max(now, expires_at) + subscription_duration` (renewals stack; upgrades take the new tier immediately).
- Emits `Subscribed`.

> Premium companion features are enforced **off-chain** by the backend reading this account (tier + expiry). On-chain only the fee tier and the bet gate depend on it.

### 3.5 `place_bet`  ⭐ core
**Args:** `outcome: Outcome`, `amount: u64`.
**Accounts:** `bettor` (signer, payer), `config`, `market` (mut), `bet` (init_if_needed, PDA), `subscription` (of bettor), `bettor_ata` (mut), `vault` (mut, == `market.vault`), `token_program`, `system_program`.
**Checks:**
1. `!config.paused`.
2. `market.status == Open`.
3. `now < market.betting_close_ts`.
4. `amount >= config.min_bet`.
5. **Bet gate:** `subscription.subscriber == bettor` **and** `now < subscription.expires_at` (any tier). Else `NotSubscribed`.
6. If `bet` already exists (`amount > 0`): `outcome == bet.outcome` (no hedging both sides). Else set `bet.outcome`.
**Effects:**
- Transfer `amount` USDC `bettor_ata → vault`.
- On first placement: snapshot `bet.fee_bps` = `premium_fee_bps` if `tier == Premium && active` else `standard_fee_bps`; set `bet.outcome`, `bet.bettor`, `bet.market`, `claimed = false`; `market.bet_count += 1`.
- `bet.amount += amount`.
- `market.pool_home/away += amount` (matching side).
- Emits `BetPlaced`.

### 3.6 `settle_market`  ⭐ oracle
**Args:** `outcome: Outcome`.
**Accounts:** `oracle_authority` (signer, == `config.oracle_authority`), `config`, `market` (mut).
**Checks:**
1. signer == `config.oracle_authority`.
2. `market.status == Open`.
3. `now >= market.betting_close_ts` (can't settle before betting closes).
4. **Empty-winning-pool guard:** if the winning side's pool == 0, the instruction instead sets `status = Voided` (there are no winners to distribute to → refund everyone). See §6.4.
**Effects (normal):** `status = Settled`, `outcome = Some(outcome)`. Emits `MarketSettled`. **No funds move here** — payouts happen lazily in `claim` (pull pattern; avoids iterating all bettors in one tx).

### 3.7 `void_market`  ⭐ oracle
**Args:** none.
**Accounts:** `oracle_authority` (signer), `config`, `market` (mut).
**Checks:** signer == oracle_authority; `market.status == Open`.
**Effects:** `status = Voided`. Emits `MarketVoided`. Used when the match result is `DRAW`, the fixture is cancelled/abandoned, or an operational error requires unwinding. Every bettor reclaims their exact stake via `claim`.

### 3.8 `claim`  ⭐ core
**Args:** none.
**Accounts:** `bettor` (signer), `config`, `market`, `bet` (mut, `has_one = bettor`, `has_one = market`), `vault` (mut), `bettor_ata` (mut), `treasury_ata` (mut, == `config.treasury_ata`), `token_program`.
**Checks:** `!bet.claimed`; `market.status` is `Settled` or `Voided`.
**Effects (branch on status):**

- **Voided:** transfer `bet.amount` `vault → bettor_ata` (full refund, no fee).
- **Settled, `bet.outcome == market.outcome`** (winner): compute payout per §6, transfer `payout` `vault → bettor`, transfer `fee` `vault → treasury_ata`, `market.fees_collected += fee`.
- **Settled, loser:** nothing transferred (their stake stays in the vault, already distributed to winners). Still set `claimed = true` so the account can be closed.

Set `bet.claimed = true`. Emits `Claimed { payout, fee, refunded }`. Vault → bettor transfers are signed by the `market` PDA. Optionally `close = bettor` on the `bet` account to reclaim rent.

### 3.9 `close_market`
**Args:** none.
**Accounts:** `admin` (signer), `config`, `market` (mut/close), `vault` (mut), `treasury_ata` (mut).
**Checks:** `market.status != Open`; a grace period past `betting_close_ts` has elapsed (e.g. 30 days) so late claimers aren't cut off.
**Effects:** Sweep any residual vault balance (rounding dust — see §6.5) to `treasury_ata`, close the vault + market accounts, reclaim rent to admin.

---

## 4. Money flow (lifecycle)

```
create_market ──▶ Open
   │                 ▲  place_bet (USDC → vault)         [gate: active subscription]
   │                 │  ... repeated by many users
   ▼
now ≥ betting_close_ts  (market effectively locked; place_bet now rejected by time check)
   │
   ├── match result HOME/AWAY ──▶ settle_market(outcome) ──▶ Settled
   │                                                            │
   │                                       winners: claim ──▶ payout + fee→treasury
   │                                       losers:  claim ──▶ (nothing; marks claimed)
   │
   └── match result DRAW / cancelled ──▶ void_market ──▶ Voided
                                                            │
                                            everyone: claim ──▶ full refund

(after grace period) close_market ──▶ sweep dust → treasury, reclaim rent
```

Subscription flow is independent: `subscribe` (USDC → treasury) any time; gates `place_bet` and sets the bettor's fee tier.

---

## 5. Oracle mapping (backend → program)

The backend maps `Match` to instructions once `status == FINISHED`:

| `Match.winner` | Program call |
|----------------|--------------|
| `HOME_TEAM` | `settle_market(Outcome::Home)` |
| `AWAY_TEAM` | `settle_market(Outcome::Away)` |
| `DRAW` | `void_market()` |
| match cancelled / `POSTPONED` past grace | `void_market()` |

The oracle transaction is signed by the Squads multisig (D6).

---

## 6. Payout & fee math

Parimutuel with **fee on profit, per bettor** (D3). Let the winning side pool = `P_win`, losing side pool = `P_lose`. For a winning bet with stake `s` and snapshot fee `f` (bps):

```
profit  = s * P_lose / P_win                 // u128 intermediate, floor division
fee     = profit * f / 10_000                // u128 intermediate
payout  = s + profit - fee                   // back to u64; ≤ s + profit
```

- `treasury` receives `fee`; the bettor receives `payout`.
- **Losers** receive nothing; their stake is exactly the `P_lose` distributed to winners.

### 6.1 Conservation check
Sum of `profit` over all winners = `Σ (s_i / P_win) * P_lose = P_lose` (modulo floor dust).
Vault held `P_win + P_lose`. Payouts return `P_win` (stakes) + `P_lose` (profit) − `Σ fee`.
Fees go to treasury. Vault nets to ~0 (plus dust). ✔ Balanced regardless of per-bettor `f`.

### 6.2 Worked example
Pools: `P_home = 800`, `P_away = 200` USDC. Outcome = HOME. Alice staked `100` on HOME, Premium fee `f = 200` (2%).

```
profit = 100 * 200 / 800 = 25
fee    = 25 * 200 / 10_000 = 0 (floor of 0.5) → 0    // small-number flooring; real amounts are 6-dp base units
payout = 100 + 25 - 0 = 125
```
With realistic 6-decimal base units (100 USDC = 100_000_000), the flooring is negligible.

### 6.3 One-sided market (`P_lose == 0`)
Every winner gets `profit = 0`, i.e. just their stake back. `fee = 0`. No losers existed. Harmless.

### 6.4 Empty winning pool (`P_win == 0`)
All money was on the losing side → no valid distribution. `settle_market` **auto-voids** (§3.6 check 4) so everyone is refunded. Prevents stuck funds.

### 6.5 Rounding dust
Floor division leaves a few base units in the vault after all winners claim. Swept to treasury by `close_market` (§3.9). Always ≤ (number of winners) base units.

### 6.6 Overflow safety
`s ≤ u64`, `P_lose ≤ u64` → `s * P_lose ≤ 2^128`. Use `u128` intermediates and Rust **checked** arithmetic (`checked_mul`/`checked_div`, `require!` on `None`). Final results fit `u64` because `payout ≤ P_win + P_lose ≤ total vault`.

---

## 7. Errors

```rust
#[error_code]
pub enum BettingError {
    ConfigAlreadyInitialized,
    Unauthorized,             // wrong admin / oracle
    Paused,
    MarketNotOpen,
    BettingClosed,            // now ≥ close_ts on place_bet
    SettleTooEarly,           // now < close_ts on settle
    BelowMinBet,
    NotSubscribed,            // bet gate failed
    OutcomeMismatch,          // hedging both sides
    AlreadyClaimed,
    MarketNotResolved,        // claim before settle/void
    InvalidMint,              // token acct mint ≠ config.usdc_mint
    InvalidTreasury,          // treasury_ata ≠ config.treasury_ata
    MathOverflow,
    GracePeriodActive,        // close_market too early
}
```

---

## 8. Events (for the backend indexer)

```rust
MarketCreated { match_id, betting_close_ts }
BetPlaced     { match_id, bettor, outcome, amount, new_pool_home, new_pool_away }
MarketSettled { match_id, outcome }
MarketVoided  { match_id }
Claimed       { match_id, bettor, payout, fee, refunded }
Subscribed    { subscriber, tier, expires_at }
```

The indexer subscribes to program logs (or Helius webhooks) and upserts the `*Mirror` tables so the UI reads SQLite, not RPC.

---

## 9. Security checklist

- [ ] `oracle_authority` is a Squads multisig, not a hot backend key (D6).
- [ ] Every token account constrained: `mint == config.usdc_mint`, `treasury_ata == config.treasury_ata`, `vault == market.vault`.
- [ ] Vault authority is the `Market` PDA; only the program can move stakes.
- [ ] `claimed` flag set before/atomically with transfer → no double claim (pull-payment pattern also avoids reentrancy surface).
- [ ] All arithmetic checked; `u128` intermediates; `require!` guards.
- [ ] `settle_market` requires `now ≥ betting_close_ts`; `place_bet` requires `now < betting_close_ts` — no settle/bet overlap.
- [ ] Empty-winning-pool auto-void (§6.4) — no stuck funds.
- [ ] `paused` kill switch on `place_bet` + `subscribe`.
- [ ] Program upgrade authority: multisig on devnet; documented freeze/timelock policy before mainnet.
- [ ] `close_market` grace period prevents cutting off late claimers.
- [ ] Fuzz the payout math (property test: Σ payouts + Σ fees == vault ± dust).

---

## 10. Test plan (Anchor / TypeScript + Rust unit)

**Happy paths**
1. init → create → subscribe(Standard) → 3 bettors place on both sides → settle(Home) → winners claim correct payouts, loser claims nothing, fees at treasury.
2. Premium bettor pays reduced fee vs Standard bettor on the same market.
3. Draw → void → all refunded exactly.

**Guards / reverts**
4. `place_bet` without active subscription → `NotSubscribed`.
5. `place_bet` after `close_ts` → `BettingClosed`.
6. `settle_market` before `close_ts` → `SettleTooEarly`.
7. Non-oracle calls `settle_market` → `Unauthorized`.
8. Double `claim` → `AlreadyClaimed`.
9. Hedging opposite side in same market → `OutcomeMismatch`.
10. Wrong mint / treasury account → `InvalidMint` / `InvalidTreasury`.

**Edge math**
11. One-sided market (all on winning side) → each refunded stake, zero fee.
12. Empty winning pool → auto-void, all refunded.
13. Property/fuzz: random pools & stakes → conservation holds within dust bound.
14. `close_market` sweeps dust to treasury; blocked during grace period.

---

## 11. Open items to confirm before coding

1. **Subscription tier pricing** — concrete numbers for `standard_price` / `premium_price` and `subscription_duration` (default proposal: 30 days).
2. **Default fees** — `standard_fee_bps` / `premium_fee_bps` (proposal: 5% / 2%).
3. **Min bet** — `min_bet` (proposal: 1 USDC).
4. **Close grace period** — how long after `betting_close_ts` before `close_market` is allowed (proposal: 30 days).
5. **Multiple bets, single side** — confirm the "no hedging both sides" rule (D7) is acceptable UX, vs. allowing separate `Bet` accounts per outcome.
```
