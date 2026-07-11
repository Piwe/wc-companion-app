import { Link, useParams } from "react-router-dom";

import Crest from "../components/Crest";
import QueryState from "../components/QueryState";
import { useMatch } from "../api/hooks";
import { formatKickoff, humanizeStage } from "../utils";

export default function Match() {
  const { id } = useParams();
  const matchQuery = useMatch(Number(id));

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-block text-sm text-pitch-700 hover:underline">
        ← Back
      </Link>

      <QueryState isLoading={matchQuery.isLoading} isError={matchQuery.isError}>
        {matchQuery.data && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-6 text-center text-sm font-semibold uppercase tracking-wide text-slate-500">
              {humanizeStage(matchQuery.data.stage)}
              {matchQuery.data.group_name ? ` · ${matchQuery.data.group_name}` : ""}
            </div>

            <div className="flex items-center justify-center gap-4">
              <div className="flex flex-1 flex-col items-center gap-2 text-center">
                <Crest url={matchQuery.data.home_team_crest} name={matchQuery.data.home_team_name} size={56} />
                <span className="font-semibold">{matchQuery.data.home_team_name ?? "TBD"}</span>
              </div>

              <div className="text-center">
                {matchQuery.data.status === "FINISHED" ? (
                  <div className="text-4xl font-bold">
                    {matchQuery.data.home_score} – {matchQuery.data.away_score}
                  </div>
                ) : (
                  <div className="text-lg font-bold text-slate-400">vs</div>
                )}
                <div className="mt-1 text-xs text-slate-500">{matchQuery.data.status}</div>
              </div>

              <div className="flex flex-1 flex-col items-center gap-2 text-center">
                <Crest url={matchQuery.data.away_team_crest} name={matchQuery.data.away_team_name} size={56} />
                <span className="font-semibold">{matchQuery.data.away_team_name ?? "TBD"}</span>
              </div>
            </div>

            <dl className="mt-8 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 px-4 py-3">
                <dt className="text-xs uppercase tracking-wide text-slate-500">Kick-off</dt>
                <dd className="font-medium">{formatKickoff(matchQuery.data.utc_date)}</dd>
              </div>
              <div className="rounded-lg bg-slate-50 px-4 py-3">
                <dt className="text-xs uppercase tracking-wide text-slate-500">Stadium</dt>
                <dd className="font-medium">{matchQuery.data.venue ?? "TBD"}</dd>
              </div>
            </dl>
          </div>
        )}
      </QueryState>
    </div>
  );
}
