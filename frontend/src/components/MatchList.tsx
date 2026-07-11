import { Link } from "react-router-dom";

import type { MatchSummary } from "../types";
import { formatKickoff, humanizeStage } from "../utils";
import Crest from "./Crest";

interface Props {
  matches: MatchSummary[];
  emptyLabel?: string;
}

function scoreOrTime(m: MatchSummary): string {
  if (m.status === "FINISHED" && m.home_score !== null && m.away_score !== null) {
    return `${m.home_score} – ${m.away_score}`;
  }
  return "vs";
}

export default function MatchList({ matches, emptyLabel = "No matches." }: Props) {
  if (matches.length === 0) {
    return <p className="py-4 text-sm text-slate-500">{emptyLabel}</p>;
  }
  return (
    <ul className="divide-y divide-slate-100">
      {matches.map((m) => (
        <li key={m.id}>
          <Link
            to={`/match/${m.id}`}
            className="flex items-center gap-3 px-1 py-3 transition hover:bg-slate-50"
          >
            <div className="w-28 shrink-0 text-xs text-slate-500">
              <div>{humanizeStage(m.stage)}</div>
              <div>{formatKickoff(m.utc_date)}</div>
            </div>
            <div className="flex flex-1 items-center justify-end gap-2 text-sm font-medium">
              <span className="truncate">{m.home_team_name ?? "TBD"}</span>
              <Crest url={m.home_team_crest} name={m.home_team_name} size={20} />
            </div>
            <div className="w-16 shrink-0 text-center text-sm font-bold">{scoreOrTime(m)}</div>
            <div className="flex flex-1 items-center gap-2 text-sm font-medium">
              <Crest url={m.away_team_crest} name={m.away_team_name} size={20} />
              <span className="truncate">{m.away_team_name ?? "TBD"}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
