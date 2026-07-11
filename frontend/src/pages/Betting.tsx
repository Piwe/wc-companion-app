import { useState } from "react";

import { api } from "../api/client";
import { useMarkets, useWalletBets } from "../api/hooks";
import BettingDisclaimer from "../components/BettingDisclaimer";
import type { MarketSummary, Outcome, PayoutPreview } from "../types";
import { shortAddress, useWallet } from "../wallet";

const USDC = 1_000_000;
const fmt = (base: number) => (base / USDC).toLocaleString(undefined, { maximumFractionDigits: 2 });
const odds = (o: number | null) => (o == null ? "—" : `${o.toFixed(2)}×`);

export default function Betting() {
  const wallet = useWallet();
  const markets = useMarkets();
  const bets = useWalletBets(wallet.publicKey);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-pitch-800">Match Winner Betting</h1>
        <WalletButton wallet={wallet} />
      </div>

      <BettingDisclaimer />

      {markets.isLoading && <p className="text-slate-500">Loading markets…</p>}
      {markets.isError && <p className="text-red-600">Failed to load markets.</p>}
      {markets.data && markets.data.length === 0 && (
        <p className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-500">
          No betting markets are open yet. An admin creates a market per match via{" "}
          <code>POST /api/betting/admin/markets</code>.
        </p>
      )}

      <div className="space-y-4">
        {markets.data?.map((m) => (
          <MarketCard key={m.match_id} market={m} walletConnected={Boolean(wallet.publicKey)} />
        ))}
      </div>

      {wallet.publicKey && bets.data && bets.data.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-2 text-lg font-semibold text-slate-700">
            Your bets ({shortAddress(wallet.publicKey)})
          </h2>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-3 py-2">Match</th>
                  <th className="px-3 py-2">Side</th>
                  <th className="px-3 py-2">Stake</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {bets.data.map((b) => (
                  <tr key={`${b.match_id}-${b.wallet}`} className="border-t border-slate-100">
                    <td className="px-3 py-2">#{b.match_id}</td>
                    <td className="px-3 py-2">{b.outcome}</td>
                    <td className="px-3 py-2">{fmt(b.amount)} USDC</td>
                    <td className="px-3 py-2">{b.claimed ? "Claimed" : "Open"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function WalletButton({ wallet }: { wallet: ReturnType<typeof useWallet> }) {
  if (wallet.publicKey) {
    return (
      <button
        onClick={wallet.disconnect}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        {shortAddress(wallet.publicKey)} · Disconnect
      </button>
    );
  }
  return (
    <button
      onClick={wallet.connect}
      disabled={wallet.connecting}
      className="rounded-md bg-pitch-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-pitch-800 disabled:opacity-60"
    >
      {wallet.connecting ? "Connecting…" : wallet.installed ? "Connect Wallet" : "Get Phantom"}
    </button>
  );
}

function MarketCard({
  market,
  walletConnected,
}: {
  market: MarketSummary;
  walletConnected: boolean;
}) {
  const [outcome, setOutcome] = useState<Outcome>("HOME");
  const [amount, setAmount] = useState("10");
  const [preview, setPreview] = useState<PayoutPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const open = market.status === "OPEN";

  const runPreview = async () => {
    const base = Math.round(parseFloat(amount || "0") * USDC);
    if (!base || base <= 0) return;
    setPreviewing(true);
    try {
      setPreview(await api.previewBet(market.match_id, outcome, base));
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-slate-800">
          {market.home_team_name ?? "Home"} <span className="text-slate-400">vs</span>{" "}
          {market.away_team_name ?? "Away"}
        </div>
        <StatusBadge market={market} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <PoolTile label={market.home_team_name ?? "HOME"} pool={market.pool_home} odd={market.odds_home} />
        <PoolTile label={market.away_team_name ?? "AWAY"} pool={market.pool_away} odd={market.odds_away} />
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Total pool {fmt(market.total_pool)} USDC · {market.bet_count} bets
      </p>

      {open && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="inline-flex overflow-hidden rounded-md border border-slate-300">
              {(["HOME", "AWAY"] as Outcome[]).map((o) => (
                <button
                  key={o}
                  onClick={() => setOutcome(o)}
                  className={`px-3 py-1.5 text-sm font-medium ${
                    outcome === o ? "bg-pitch-700 text-white" : "bg-white text-slate-600"
                  }`}
                >
                  {o === "HOME" ? market.home_team_name ?? "HOME" : market.away_team_name ?? "AWAY"}
                </button>
              ))}
            </div>
            <label className="text-sm text-slate-600">
              Stake (USDC)
              <input
                type="number"
                min="0"
                step="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="ml-2 w-24 rounded-md border border-slate-300 px-2 py-1"
              />
            </label>
            <button
              onClick={runPreview}
              disabled={previewing}
              className="rounded-md border border-pitch-700 px-3 py-1.5 text-sm font-medium text-pitch-800 hover:bg-pitch-50 disabled:opacity-60"
            >
              {previewing ? "…" : "Preview payout"}
            </button>
          </div>

          {preview && (
            <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
              If <strong>{preview.outcome}</strong> wins: projected payout{" "}
              <strong>{fmt(preview.projected_payout)} USDC</strong> (profit{" "}
              {fmt(preview.projected_profit)}, fee {fmt(preview.projected_fee)}) · effective odds{" "}
              {odds(preview.odds)}
            </div>
          )}

          <button
            disabled
            title="On-chain betting is not live yet — deploy the wc_betting program first."
            className="mt-3 w-full cursor-not-allowed rounded-md bg-slate-300 py-2 text-sm font-semibold text-slate-600"
          >
            {walletConnected ? "Place bet (on-chain — coming soon)" : "Connect wallet to bet"}
          </button>
        </div>
      )}

      {market.status === "SETTLED" && (
        <p className="mt-3 text-sm text-slate-600">
          Settled — winner: <strong>{market.outcome}</strong>
        </p>
      )}
      {market.status === "VOIDED" && (
        <p className="mt-3 text-sm text-slate-600">Voided — all stakes refundable.</p>
      )}
    </div>
  );
}

function PoolTile({ label, pool, odd }: { label: string; pool: number; odd: number | null }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="truncate text-sm font-medium text-slate-700">{label}</div>
      <div className="mt-1 text-lg font-bold text-pitch-800">{odds(odd)}</div>
      <div className="text-xs text-slate-400">{fmt(pool)} USDC staked</div>
    </div>
  );
}

function StatusBadge({ market }: { market: MarketSummary }) {
  const styles: Record<string, string> = {
    OPEN: "bg-green-100 text-green-800",
    SETTLED: "bg-slate-200 text-slate-700",
    VOIDED: "bg-amber-100 text-amber-800",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${styles[market.status]}`}>
      {market.status}
    </span>
  );
}
