import type {
  BetSummary,
  GroupDetail,
  GroupSummary,
  MarketSummary,
  MatchSummary,
  Outcome,
  PayoutPreview,
  TeamMatches,
  TeamStatus,
  TeamSummary,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listTeams: (q?: string) =>
    get<TeamSummary[]>(`/api/teams${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  teamStatus: (id: number) => get<TeamStatus>(`/api/teams/${id}`),
  listGroups: () => get<GroupSummary[]>("/api/groups"),
  groupDetail: (name: string) => get<GroupDetail>(`/api/groups/${encodeURIComponent(name)}`),
  teamMatches: (id: number) => get<TeamMatches>(`/api/matches/team/${id}`),
  matchDetail: (id: number) => get<MatchSummary>(`/api/matches/${id}`),

  // Betting
  listMarkets: () => get<MarketSummary[]>("/api/betting/markets"),
  market: (matchId: number) => get<MarketSummary>(`/api/betting/markets/${matchId}`),
  previewBet: (matchId: number, outcome: Outcome, amount: number, tier = "STANDARD") =>
    get<PayoutPreview>(
      `/api/betting/markets/${matchId}/preview?outcome=${outcome}&amount=${amount}&tier=${tier}`,
    ),
  walletBets: (wallet: string) =>
    get<BetSummary[]>(`/api/betting/wallets/${encodeURIComponent(wallet)}/bets`),
};
