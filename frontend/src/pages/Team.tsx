import { Link, useParams } from "react-router-dom";

import KnockoutPath from "../components/KnockoutPath";
import MatchList from "../components/MatchList";
import QueryState from "../components/QueryState";
import StandingsTable from "../components/StandingsTable";
import StatusCard from "../components/StatusCard";
import { useGroup, useTeamMatches, useTeamStatus } from "../api/hooks";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-bold">{title}</h2>
      {children}
    </section>
  );
}

export default function Team() {
  const { id } = useParams();
  const teamId = Number(id);
  const statusQuery = useTeamStatus(teamId);
  const matchesQuery = useTeamMatches(teamId);
  const groupName = statusQuery.data?.team.group_name ?? "";
  const groupQuery = useGroup(groupName);

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-block text-sm text-pitch-700 hover:underline">
        ← Back
      </Link>

      <QueryState isLoading={statusQuery.isLoading} isError={statusQuery.isError}>
        {statusQuery.data && (
          <>
            <StatusCard
              team={statusQuery.data.team}
              standing={statusQuery.data.standing}
              progression={statusQuery.data.progression}
            />

            <Section title="Knockout path">
              <KnockoutPath path={statusQuery.data.knockout_path} />
            </Section>

            {groupName && groupQuery.data && (
              <Section title={`${groupName} standings`}>
                <StandingsTable
                  rows={groupQuery.data.standings}
                  highlightTeamId={teamId}
                />
              </Section>
            )}

            <Section title="Matches">
              <QueryState isLoading={matchesQuery.isLoading} isError={matchesQuery.isError}>
                {matchesQuery.data && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="mb-1 text-sm font-semibold text-slate-500">Results</h3>
                      <MatchList matches={matchesQuery.data.past} emptyLabel="No matches played yet." />
                    </div>
                    <div>
                      <h3 className="mb-1 text-sm font-semibold text-slate-500">Upcoming</h3>
                      <MatchList
                        matches={matchesQuery.data.upcoming}
                        emptyLabel="No upcoming fixtures."
                      />
                    </div>
                  </div>
                )}
              </QueryState>
            </Section>
          </>
        )}
      </QueryState>
    </div>
  );
}
