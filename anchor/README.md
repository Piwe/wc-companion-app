# wc_betting — Anchor program

Parimutuel match-winner betting + tiered subscriptions on Solana. Implements
[`../betting-program-spec.md`](../betting-program-spec.md).

## ⚠️ Toolchain required — cannot be built in the bare app environment

This crate needs the Solana/Anchor toolchain, which is **not** installed alongside the
web app. Install it before `build`/`test`:

```bash
# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Solana CLI
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"

# Anchor (via avm)
cargo install --git https://github.com/coral-xyz/anchor avm --locked
avm install 0.30.1 && avm use 0.30.1

# Node deps for the TS tests
yarn install   # or: npm install
```

## Build, test, deploy (devnet)

```bash
anchor build
anchor keys sync          # writes the real program id into lib.rs + Anchor.toml
anchor test               # localnet integration tests
anchor deploy --provider.cluster devnet
```

After deploy, copy the program id into the backend (`BETTING_PROGRAM_ID`) and the
frontend, and generate the client IDL/types from `target/idl/wc_betting.json`.

## Layout

| File | Purpose |
|------|---------|
| `programs/wc_betting/src/lib.rs` | instructions + account contexts + payout math |
| `programs/wc_betting/src/state.rs` | `Config` / `Market` / `Bet` / `Subscription` + enums |
| `programs/wc_betting/src/error.rs` | `BettingError` codes |
| `programs/wc_betting/src/events.rs` | events consumed by the backend indexer |
| `tests/wc_betting.ts` | happy-path integration test |

The program id in `lib.rs` (`declare_id!`) and `Anchor.toml` is a **placeholder** —
`anchor keys sync` replaces it with the keypair generated at first build.
