import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-4 px-4 py-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-pitch-800">
            <span className="text-xl">⚽</span>
            World Cup 2026 Companion
          </Link>
          <nav className="ml-auto">
            <Link to="/betting" className="text-sm font-semibold text-pitch-700 hover:text-pitch-800">
              Betting
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6">{children}</main>
      <footer className="mx-auto max-w-4xl px-4 py-8 text-center text-xs text-slate-400">
        Data via Football-Data.org · refreshed daily
      </footer>
    </div>
  );
}
