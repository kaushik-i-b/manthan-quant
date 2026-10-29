"use client";
import { useLive } from "@/hooks/useLive";

function Dot({ ok, warn }: { ok: boolean; warn?: boolean }) {
  return <span className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-profit" : warn ? "bg-warn" : "bg-loss"}`} />;
}

export function Topbar({ ws, stale }: { ws: boolean; stale: boolean }) {
  const { health } = useLive();
  const live = health?.trading_enabled ? false : true;
  const simLive = health?.stage === "TRADING";
  return (
    <header className="sticky top-0 z-10 bg-bg/95 backdrop-blur border-b border-bord px-4 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border font-semibold ${simLive ? "border-profit/40 text-profit" : "border-warn/40 text-warn"}`}>
        <span className={`w-2 h-2 rounded-full ${simLive ? "bg-profit animate-pulse" : "bg-warn"}`} />
        {simLive ? "TRADING ACTIVE" : `STAGE: ${health?.stage ?? "…"}`}
      </div>
      <div className="px-3 py-1.5 rounded-full border border-bord text-muted font-semibold">
        {health?.dry_run ? "DRY RUN" : "LIVE SIMULATION"}
      </div>
      <div className="flex items-center gap-4 text-muted ml-auto">
        <span className="flex items-center gap-1.5"><Dot ok={ws && !stale} /> WS {ws ? (stale ? "stale" : "live") : "down"}</span>
        <span className="flex items-center gap-1.5"><Dot ok={health?.heartbeat_ok ?? false} /> HB</span>
        <span className="flex items-center gap-1.5"><Dot ok={health?.api_ok ?? true} /> API</span>
        <span>Day <b className="text-ink">{health?.sim_day ?? "—"}</b></span>
        <span className="hidden lg:inline">Decisions <b className="text-ink">{health?.decisions ?? 0}</b> · {health?.avg_decision_ms ?? 0} ms</span>
      </div>
    </header>
  );
}
