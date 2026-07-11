import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Crest from "../components/Crest";
import GroupList from "../components/GroupList";
import QueryState from "../components/QueryState";
import SearchBar from "../components/SearchBar";
import { useGroups, useTeams } from "../api/hooks";

export default function Home() {
  const [query, setQuery] = useState("");
  const groupsQuery = useGroups();
  const teamsQuery = useTeams();

  const results = useMemo(() => {
    const teams = teamsQuery.data ?? [];
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return teams.filter((t) => t.name.toLowerCase().includes(q)).slice(0, 8);
  }, [teamsQuery.data, query]);

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-xl font-bold">Find your team</h2>
        <SearchBar value={query} onChange={setQuery} />
        {results.length > 0 && (
          <ul className="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
            {results.map((t) => (
              <li key={t.id}>
                <Link
                  to={`/team/${t.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50"
                >
                  <Crest url={t.crest_url} name={t.name} size={24} />
                  <span className="font-medium">{t.name}</span>
                  <span className="ml-auto text-sm text-slate-400">{t.group_name}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold">Groups</h2>
        <QueryState isLoading={groupsQuery.isLoading} isError={groupsQuery.isError}>
          <GroupList groups={groupsQuery.data ?? []} />
        </QueryState>
      </section>
    </div>
  );
}
