/**
 * Happy-path integration test for wc_betting.
 *
 * Mirrors betting-program-spec.md §6.2: pools HOME 800 / AWAY 200, a 100-USDC
 * premium (2% fee) bet on HOME wins => 124.5 USDC payout, 0.5 USDC fee.
 *
 * Requires the Solana/Anchor toolchain (see README). Run with `anchor test`.
 */
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import {
  createMint,
  getOrCreateAssociatedTokenAccount,
  mintTo,
  getAccount,
} from "@solana/spl-token";
import { assert } from "chai";
import { WcBetting } from "../target/types/wc_betting";

const USDC = 1_000_000; // 1 USDC (6 decimals)
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("wc_betting", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.WcBetting as Program<WcBetting>;
  const conn = provider.connection;
  const payer = (provider.wallet as anchor.Wallet).payer;

  const oracle = anchor.web3.Keypair.generate();
  const alice = anchor.web3.Keypair.generate(); // premium, HOME 100
  const whale = anchor.web3.Keypair.generate(); // standard, HOME 700
  const bob = anchor.web3.Keypair.generate(); // standard, AWAY 200

  const matchId = new anchor.BN(995001);
  let mint: anchor.web3.PublicKey;
  let treasuryAta: anchor.web3.PublicKey;
  let configPda: anchor.web3.PublicKey;
  let marketPda: anchor.web3.PublicKey;
  let vaultPda: anchor.web3.PublicKey;

  const pda = (seeds: (Buffer | Uint8Array)[]) =>
    anchor.web3.PublicKey.findProgramAddressSync(seeds, program.programId)[0];

  const airdrop = async (kp: anchor.web3.Keypair) => {
    const sig = await conn.requestAirdrop(kp.publicKey, 2 * anchor.web3.LAMPORTS_PER_SOL);
    await conn.confirmTransaction(sig);
  };

  before(async () => {
    for (const kp of [oracle, alice, whale, bob]) await airdrop(kp);

    mint = await createMint(conn, payer, payer.publicKey, null, 6);
    treasuryAta = (
      await getOrCreateAssociatedTokenAccount(conn, payer, mint, payer.publicKey)
    ).address;

    configPda = pda([Buffer.from("config")]);
    marketPda = pda([Buffer.from("market"), matchId.toArrayLike(Buffer, "le", 8)]);
    vaultPda = pda([Buffer.from("vault"), marketPda.toBuffer()]);
  });

  const fund = async (kp: anchor.web3.Keypair, amount: number) => {
    const ata = await getOrCreateAssociatedTokenAccount(conn, payer, mint, kp.publicKey);
    await mintTo(conn, payer, mint, ata.address, payer, amount);
    return ata.address;
  };

  const subPda = (owner: anchor.web3.PublicKey) =>
    pda([Buffer.from("subscription"), owner.toBuffer()]);
  const betPda = (owner: anchor.web3.PublicKey) =>
    pda([Buffer.from("bet"), marketPda.toBuffer(), owner.toBuffer()]);

  it("initializes config", async () => {
    await program.methods
      .initializeConfig(
        oracle.publicKey,
        500, // standard fee bps (5%)
        200, // premium fee bps (2%)
        new anchor.BN(5 * USDC), // standard price
        new anchor.BN(20 * USDC), // premium price
        new anchor.BN(30 * 24 * 60 * 60), // 30 day duration
        new anchor.BN(USDC) // min bet 1 USDC
      )
      .accounts({ admin: payer.publicKey, usdcMint: mint, treasuryAta })
      .rpc();

    const cfg = await program.account.config.fetch(configPda);
    assert.equal(cfg.standardFeeBps, 500);
    assert.equal(cfg.premiumFeeBps, 200);
  });

  it("creates a market", async () => {
    const closeTs = Math.floor(Date.now() / 1000) + 5;
    await program.methods
      .createMarket(matchId, 990001, 990002, new anchor.BN(closeTs))
      .accounts({
        oracleAuthority: oracle.publicKey,
        market: marketPda,
        vault: vaultPda,
        usdcMint: mint,
      })
      .signers([oracle])
      .rpc();

    const m = await program.account.market.fetch(marketPda);
    assert.deepEqual(m.status, { open: {} });
  });

  const subscribe = async (kp: anchor.web3.Keypair, tier: object) => {
    const ata = await fund(kp, 1000 * USDC);
    await program.methods
      .subscribe(tier as never)
      .accounts({
        subscriber: kp.publicKey,
        subscriberAta: ata,
        treasuryAta,
        subscription: subPda(kp.publicKey),
      })
      .signers([kp])
      .rpc();
    return ata;
  };

  const placeBet = async (
    kp: anchor.web3.Keypair,
    ata: anchor.web3.PublicKey,
    outcome: object,
    amount: number
  ) => {
    await program.methods
      .placeBet(outcome as never, new anchor.BN(amount))
      .accounts({
        bettor: kp.publicKey,
        market: marketPda,
        bet: betPda(kp.publicKey),
        subscription: subPda(kp.publicKey),
        bettorAta: ata,
        vault: vaultPda,
      })
      .signers([kp])
      .rpc();
  };

  it("takes bets, settles HOME, pays the winner per spec", async () => {
    const aliceAta = await subscribe(alice, { premium: {} });
    const whaleAta = await subscribe(whale, { standard: {} });
    const bobAta = await subscribe(bob, { standard: {} });

    await placeBet(alice, aliceAta, { home: {} }, 100 * USDC);
    await placeBet(whale, whaleAta, { home: {} }, 700 * USDC);
    await placeBet(bob, bobAta, { away: {} }, 200 * USDC);

    const m = await program.account.market.fetch(marketPda);
    assert.equal(m.poolHome.toNumber(), 800 * USDC);
    assert.equal(m.poolAway.toNumber(), 200 * USDC);
    assert.equal(m.betCount, 3);

    await sleep(6000); // let betting_close_ts pass

    await program.methods
      .settleMarket({ home: {} } as never)
      .accounts({ oracleAuthority: oracle.publicKey, market: marketPda })
      .signers([oracle])
      .rpc();

    const before = (await getAccount(conn, aliceAta)).amount;
    await program.methods
      .claim()
      .accounts({
        bettor: alice.publicKey,
        market: marketPda,
        bet: betPda(alice.publicKey),
        vault: vaultPda,
        bettorAta: aliceAta,
        treasuryAta,
      })
      .signers([alice])
      .rpc();
    const after = (await getAccount(conn, aliceAta)).amount;

    // Alice staked 100; parimutuel profit = 100*200/800 = 25; premium fee 2% of 25 = 0.5.
    assert.equal(Number(after - before), 124 * USDC + 500_000);
  });
});
