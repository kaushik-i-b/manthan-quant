"use client";
import { useEffect, useState } from "react";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { api } from "@/lib/api";

interface RiskState { paused: boolean; pause_reason: string; current_drawdown_pct: number; max_drawdown_pct: number; exposure_pct: number; cash_reserve_pct: number; min_cash_pct: number; orders_today: number; max_orders_day: number; violations: { reason: string }[]; limits: Record<string, number>; }

function RiskInner() {
  const [r, setR] = useState<RiskState | null>(null);
  const { health } = useLive();
  const load = () => api<RiskState>("/api/risk").then(setR).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [health?.sim_day]);
  if (!r) return <Empty msg="Loading risk state…" />;
  const ok = !r.paused && r.current_drawdown_pct < r.max_drawdown_pct && r.cash_reserve_pct >= r.min_cash_pct;
  return (
    <div className="space-y-3">
      <Card title="Risk health" sub="Independent engine — blocks unsafe signals before execution"
        right={<span className={`px-3 py-1.5 rounded-full text-xs font-bold ${ok ? "bg-profit/15 text-profit" : "bg-loss/15 text-loss"}`}>{ok ? "HEALTHY" : r.paused ? "PAUSED" : "BREACH"}</span>}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm num">
          {[["Drawdown", `${r.current_drawdown_pct.toFixed(2)}% / ${r.max_drawdown_pct}%`], ["Exposure", `${r.exposure_pct.toFixed(1)}%`], ["Cash reserve", `${r.cash_reserve_pct.toFixed(1)}% (min ${r.min_cash_pct}%)`], ["Orders today", `${r.orders_today}/${r.max_orders_day}`]].map(([k, v]) => (
            <div key={k} className="bg-surface border border-bord rounded-lg p-3"><div className="text-[11px] text-muted uppercase">{k}</div><b>{v}</b></div>))}
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={() => api("/api/risk/pause", { method: "POST", body: JSON.stringify({ paused: true, reason: "manual dashboard pause" }) }).then(load)} className="px-4 py-2 rounded-lg bg-loss/15 text-loss border border-loss/30 text-sm font-semibold">Pause trading</button>
          <button onClick={() => api("/api/risk/pause", { method: "POST", body: JSON.stringify({ paused: false }) }).then(load)} className="px-4 py-2 rounded-lg bg-profit/15 text-profit border border-profit/30 text-sm font-semibold">Resume</button>
          {r.paused && <span className="text-xs text-warn self-center">Paused: {r.pause_reason}</span>}
        </div>
      </Card>
      <Card title="Limits" sub="Configurable — env driven">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs num">
          {Object.entries(r.limits).map(([k, v]) => <div key={k} className="flex justify-between border-b border-bord/50 py-1.5"><span className="text-muted">{k}</span><b>{v}%</b></div>)}
        </div>
      </Card>
      <Card title="Rejected signals" sub="Risk engine vetoes with reasons">
        {r.violations.length === 0 ? <Empty msg="No violations — all clear." /> : (
          <div className="space-y-1.5 max-h-64 overflow-auto">{r.violations.slice().reverse().map((v, i) => (
            <div key={i} className="text-xs border border-warn/30 bg-warn/5 rounded-lg p-2">{v.reason}</div>))}</div>)}
      </Card>
    </div>
  );
}
export default function Page() { return <Providers><RiskInner /></Providers>; }
