import { Link } from "react-router-dom";

import type { StandingRow } from "../types";
import Crest from "./Crest";

interface Props {
  rows: StandingRow[];
  highlightTeamId?: number;
}

/** Position badge: green = direct qualification (top 2), amber = 3rd (best-third contention). */
function positionColor(position: number): string {
  if (position <= 2) return "bg-pitch-600";
  if (position === 3) return "bg-amber-500";
  return "bg-slate-400";
}

export default function StandingsTable({ rows, highlightTeamId }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pl-2 pr-2">#</th>
            <th className="py-2 pr-2">Team</th>
            <th className="py-2 px-2 text-center">P</th>
            <th className="py-2 px-2 text-center">W</th>
            <th className="py-2 px-2 text-center">D</th>
            <th className="py-2 px-2 text-center">L</th>
            <th className="py-2 px-2 text-center">GF</th>
            <th className="py-2 px-2 text-center">GA</th>
            <th className="py-2 px-2 text-center">GD</th>
            <th className="py-2 px-2 text-center font-bold">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.team_id}
              className={`border-b border-slate-100 ${
                r.team_id === highlightTeamId ? "bg-pitch-50" : ""
              }`}
            >
              <td className="py-2 pl-2 pr-2">
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold text-white ${positionColor(
                    r.position,
                  )}`}
                >
                  {r.position}
                </span>
              </td>
              <td className="py-2 pr-2">
                <Link
                  to={`/team/${r.team_id}`}
                  className="flex items-center gap-2 font-medium hover:text-pitch-700"
                >
                  <Crest url={r.crest_url} name={r.team_name} size={20} />
                  {r.team_name}
                </Link>
              </td>
              <td className="py-2 px-2 text-center">{r.played}</td>
              <td className="py-2 px-2 text-center">{r.won}</td>
              <td className="py-2 px-2 text-center">{r.draw}</td>
              <td className="py-2 px-2 text-center">{r.lost}</td>
              <td className="py-2 px-2 text-center">{r.goals_for}</td>
              <td className="py-2 px-2 text-center">{r.goals_against}</td>
              <td className="py-2 px-2 text-center">
                {r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference}
              </td>
              <td className="py-2 px-2 text-center font-bold">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
