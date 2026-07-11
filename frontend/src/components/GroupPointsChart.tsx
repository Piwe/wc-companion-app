import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { StandingRow } from "../types";

interface Props {
  rows: StandingRow[];
}

/** Simple visual required by the concept (§4.2 / §9): points per team in the group. */
export default function GroupPointsChart({ rows }: Props) {
  const data = rows.map((r) => ({
    name: r.team_name.length > 10 ? `${r.team_name.slice(0, 9)}…` : r.team_name,
    points: r.points,
    gd: r.goal_difference,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="points" fill="#16a34a" radius={[4, 4, 0, 0]} name="Points" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
