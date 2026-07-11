import { Link } from "react-router-dom";

import type { KnockoutStep } from "../types";
import { formatDay, humanizeStage } from "../utils";

const RESULT_STYLE: Record<KnockoutStep["result"], string> = {
  won: "border-pitch-600 bg-pitch-50",
  lost: "border-red-400 bg-red-50",
  draw: "border-slate-300 bg-slate-50",
  upcoming: "border-dashed border-slate-300 bg-white",
};

const RESULT_LABEL: Record<KnockoutStep["result"], string> = {
  won: "Won",
  lost: "Lost",
  draw: "Draw",
  upcoming: "Upcoming",
};

interface Props {
  path: KnockoutStep[];
}

export default function KnockoutPath({ path }: Props) {
  if (path.length === 0) {
    return <p className="text-sm text-slate-500">Not yet in the knockout stage.</p>;
  }
  return (
    <ol className="space-y-2">
      {path.map((step) => (
        <li key={step.match_id}>
          <Link
            to={`/match/${step.match_id}`}
            className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition hover:shadow-sm ${
              RESULT_STYLE[step.result]
            }`}
          >
            <div className="flex-1">
              <div className="text-sm font-semibold">{humanizeStage(step.stage)}</div>
              <div className="text-xs text-slate-500">
                vs {step.opponent_name ?? "TBD"} · {formatDay(step.utc_date)}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold">{step.score ?? "—"}</div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500">
                {RESULT_LABEL[step.result]}
              </div>
            </div>
          </Link>
        </li>
      ))}
    </ol>
  );
}
