import type { ReactNode } from "react";

interface Props {
  isLoading: boolean;
  isError: boolean;
  children: ReactNode;
}

/** Uniform loading / error wrapper for query-backed views. */
export default function QueryState({ isLoading, isError, children }: Props) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-pitch-600" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700">
        <p className="font-semibold">Could not load data.</p>
        <p className="mt-1 text-sm">Is the backend running at the configured VITE_API_URL?</p>
      </div>
    );
  }
  return <>{children}</>;
}
