import type { Progression, StandingRow, TeamSummary } from "../types";
import Crest from "./Crest";

interface Props {
  team: TeamSummary;
  standing: StandingRow | null;
  progression: Progression;
}

function statusStyle(p: Progression): string {
  if (p.eliminated) return "bg-red-100 text-red-800";
  if (p.qualified) return "bg-pitch-100 text-pitch-800";
  return "bg-amber-100 text-amber-800";
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

export default function StatusCard({ team, standing, progression }: Props) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <Crest url={team.crest_url} name={team.name} size={44} />
        <div>
          <h1 className="text-2xl font-bold">{team.name}</h1>
          <p className="text-sm text-slate-500">{team.group_name ?? "—"}</p>
        </div>
        <span
          className={`ml-auto rounded-full px-3 py-1 text-sm font-semibold ${statusStyle(
            progression,
          )}`}
        >
          {progression.status}
        </span>
      </div>

      {standing ? (
        <div className="mt-5 grid grid-cols-4 gap-2 sm:grid-cols-8">
          <Stat label="Pos" value={standing.position} />
          <Stat label="Pld" value={standing.played} />
          <Stat label="Pts" value={standing.points} />
          <Stat label="W" value={standing.won} />
          <Stat label="D" value={standing.draw} />
          <Stat label="L" value={standing.lost} />
          <Stat label="GF/GA" value={`${standing.goals_for}/${standing.goals_against}`} />
          <Stat
            label="GD"
            value={standing.goal_difference > 0 ? `+${standing.goal_difference}` : standing.goal_difference}
          />
        </div>
      ) : (
        <p className="mt-5 text-sm text-slate-500">No group standing available.</p>
      )}
    </div>
  );
}
