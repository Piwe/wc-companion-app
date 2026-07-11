import { Link, useParams } from "react-router-dom";

import GroupPointsChart from "../components/GroupPointsChart";
import MatchList from "../components/MatchList";
import QueryState from "../components/QueryState";
import StandingsTable from "../components/StandingsTable";
import { useGroup } from "../api/hooks";

export default function Group() {
  const { name } = useParams();
  const groupName = decodeURIComponent(name ?? "");
  const groupQuery = useGroup(groupName);

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-block text-sm text-pitch-700 hover:underline">
        ← Back
      </Link>
      <h1 className="text-2xl font-bold">{groupName}</h1>

      <QueryState isLoading={groupQuery.isLoading} isError={groupQuery.isError}>
        {groupQuery.data && (
          <>
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 text-lg font-bold">Standings</h2>
              <StandingsTable rows={groupQuery.data.standings} />
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 text-lg font-bold">Points</h2>
              <GroupPointsChart rows={groupQuery.data.standings} />
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 text-lg font-bold">Remaining fixtures</h2>
              <MatchList
                matches={groupQuery.data.remaining_fixtures}
                emptyLabel="All group matches have been played."
              />
            </section>
          </>
        )}
      </QueryState>
    </div>
  );
}
