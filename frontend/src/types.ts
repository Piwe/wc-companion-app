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
