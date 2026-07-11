/**
 * Banner shown on the Betting page. The parimutuel odds, pools and payout previews
 * are live from the backend, but placing real bets needs the on-chain wc_betting
 * program deployed to Solana devnet — which requires the Solana/Anchor toolchain.
 */
export default function BettingDisclaimer() {
  return (
    <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="font-semibold">⚠️ Preview only — on-chain betting not yet live</p>
      <p className="mt-1 leading-relaxed">
        Odds, pools and payout projections below are computed by the backend using the same
        parimutuel math as the smart contract. Actually placing bets, subscribing and claiming
        winnings runs against the <code className="rounded bg-amber-100 px-1">wc_betting</code>{" "}
        Solana program, which must first be built and deployed to devnet. That step requires the
        <strong> Solana / Anchor toolchain</strong> (Rust, Solana CLI, Anchor) — see{" "}
        <code className="rounded bg-amber-100 px-1">anchor/README.md</code>. Until then, bet
        actions are disabled.
      </p>
    </div>
  );
}
