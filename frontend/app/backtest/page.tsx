"use client";
import { useState } from "react";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

function LabInner() {
  const [strat, setStrat] = useState("all");
  const [res, setRes] = useState<Record<string, { total_return_pct: number; max_drawdown_pct: number; sharpe: number; trades: number; win_rate_pct: number; fees: number; final_equity: number } & Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  async function run() {
    setLoading(true); setErr("");
    try { setRes(await api("/api/backtest", { method: "POST", body: JSON.stringify({ strategy: strat, seed: 42 }) })); }
    catch (e) { setErr(String(e)); }
    setLoading(false);
  }
  const rows = res ? Object.entries(res).filter(([k]) => !["buy_hold_baseline_pct", "note"].includes(k)) : [];
  return (
    <div className="space-y-3">
      <Card title="Backtest Lab" sub="Backend-only runs · chronological splits · no lookahead · synthetic data labeled">
        <div className="flex flex-wrap gap-2 items-center">
          <select value={strat} onChange={(e) => setStrat(e.target.value)} className="bg-surface border border-bord rounded-lg px-3 py-2 text-sm">
            <option value="all">All strategies</option><option value="adaptive">Adaptive</option>
            <option value="trend">Trend</option><option value="meanrev">Mean reversion</option><option value="breakout">Breakout</option>
          </select>
          <button onClick={run} disabled={loading} className="px-5 py-2 rounded-lg bg-accent/15 text-accent border border-accent/30 text-sm font-bold disabled:opacity-50">{loading ? "Running…" : "Run backtest"}</button>
          {res?.note && <span className="text-xs text-muted">{String(res.note)}</span>}
          {err && <span className="text-xs text-loss">{err}</span>}
        </div>
      </Card>
      {rows.length > 0 && (
        <Card title="Results" sub={`Buy & hold baseline: ${res?.buy_hold_baseline_pct}%`}>
          <div className="overflow-auto"><table className="w-full text-xs num">
            <thead><tr className="text-muted text-left"><th>Strategy</th><th>Return%</th><th>MaxDD%</th><th>Sharpe</th><th>Trades</th><th>Win%</th><th>Fees</th><th>Final ₹</th></tr></thead>
            <tbody>{rows.map(([k, v]) => (
              <tr key={k} className="border-t border-bord"><td className="py-2 font-bold">{k}</td>
                <td className={v.total_return_pct >= 0 ? "text-profit" : "text-loss"}>{v.total_return_pct}%</td>
                <td>{v.max_drawdown_pct}%</td><td>{v.sharpe}</td><td>{v.trades}</td><td>{v.win_rate_pct}%</td><td>₹{v.fees}</td><td>₹{Number(v.final_equity).toLocaleString("en-IN")}</td></tr>))}
            </tbody>
          </table></div>
        </Card>)}
      {!res && !loading && <Empty msg="Pick a strategy and run — results appear here." />}
    </div>
  );
}
export default function Page() { return <Providers><LabInner /></Providers>; }
