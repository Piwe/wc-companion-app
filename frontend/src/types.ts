export interface TeamSummary {
  id: number;
  name: string;
  tla: string | null;
  crest_url: string | null;
  group_name: string | null;
}

export interface StandingRow {
  team_id: number;
  team_name: string;
  crest_url: string | null;
  position: number;
  played: number;
  won: number;
  draw: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}

export interface MatchSummary {
  id: number;
  stage: string;
  group_name: string | null;
  matchday: number | null;
  status: string;
  utc_date: string | null;
  venue: string | null;
  home_team_id: number | null;
  away_team_id: number | null;
  home_team_name: string | null;
  away_team_name: string | null;
  home_team_crest: string | null;
  away_team_crest: string | null;
  home_score: number | null;
  away_score: number | null;
  winner: string | null;
}

export interface KnockoutStep {
  stage: string;
  match_id: number;
  opponent_name: string | null;
  utc_date: string | null;
  result: "won" | "lost" | "draw" | "upcoming";
  score: string | null;
}

export interface Progression {
  status: string;
  qualified: boolean;
  eliminated: boolean;
}

export interface GroupSummary {
  name: string;
  standings: StandingRow[];
}

export interface GroupDetail {
  name: string;
  standings: StandingRow[];
  remaining_fixtures: MatchSummary[];
}

export interface TeamStatus {
  team: TeamSummary;
  standing: StandingRow | null;
  progression: Progression;
  upcoming_fixtures: MatchSummary[];
  knockout_path: KnockoutStep[];
}

export interface TeamMatches {
  team: TeamSummary;
  past: MatchSummary[];
  upcoming: MatchSummary[];
}

// --- Betting layer ---

export type MarketStatus = "OPEN" | "SETTLED" | "VOIDED";
export type Outcome = "HOME" | "AWAY";

export interface MarketSummary {
  match_id: number;
  status: MarketStatus;
  outcome: Outcome | null;
  betting_close_ts: string | null;
  pool_home: number;
  pool_away: number;
  total_pool: number;
  bet_count: number;
  odds_home: number | null;
  odds_away: number | null;
  market_pubkey: string | null;
  stage: string | null;
  group_name: string | null;
  utc_date: string | null;
  home_team_id: number | null;
  away_team_id: number | null;
  home_team_name: string | null;
  away_team_name: string | null;
  home_team_crest: string | null;
  away_team_crest: string | null;
}

export interface PayoutPreview {
  outcome: Outcome;
  stake: number;
  projected_profit: number;
  projected_fee: number;
  projected_payout: number;
  odds: number | null;
}

export interface BetSummary {
  match_id: number;
  wallet: string;
  outcome: Outcome;
  amount: number;
  fee_bps: number;
  claimed: boolean;
  tx_signature: string | null;
}
