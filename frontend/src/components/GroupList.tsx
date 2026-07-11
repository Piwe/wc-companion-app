import { Link } from "react-router-dom";

import type { GroupSummary } from "../types";
import Crest from "./Crest";

interface Props {
  groups: GroupSummary[];
}

export default function GroupList({ groups }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {groups.map((g) => (
        <Link
          key={g.name}
          to={`/group/${encodeURIComponent(g.name)}`}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-pitch-600 hover:shadow"
        >
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            {g.name}
          </h3>
          <ul className="space-y-1.5">
            {g.standings.map((r) => (
              <li key={r.team_id} className="flex items-center gap-2 text-sm">
                <span className="w-4 text-xs text-slate-400">{r.position}</span>
                <Crest url={r.crest_url} name={r.team_name} size={18} />
                <span className="flex-1 truncate">{r.team_name}</span>
                <span className="font-semibold">{r.points}</span>
              </li>
            ))}
          </ul>
        </Link>
      ))}
    </div>
  );
}
