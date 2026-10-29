"use client";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

function StratInner() {
  const { signals } = useLive();
  const byStrat: Record<string, { n: number; buy: number; sell: number }> = {};
  signals.forEach((s) => {
    byStrat[s.strategy] = byStrat[s.strategy] || { n: 0, buy: 0, sell: 0 };
    byStrat[s.strategy].n++;
    if (s.action === "BUY") byStrat[s.strategy].buy++;
    if (s.action === "SELL") byStrat[s.strategy].sell++;
  });
  const data = Object.entries(byStrat).map(([k, v]) => ({ strategy: k, ...v }));
  const latest = signals[0];
  return (
    <div className="space-y-3">
      {latest && (
        <Card title="Decision explanation" sub="Every trade carries its reasoning — no invented narratives">
          <div className="grid md:grid-cols-4 gap-3 text-sm">
            <div><div className="text-muted text-xs">Ticker</div><b className="text-lg">{latest.ticker}</b></div>
            <div><div className="text-muted text-xs">Action</div><b className={`text-lg ${latest.action === "BUY" ? "text-profit" : latest.action === "SELL" ? "text-loss" : ""}`}>{latest.action}</b></div>
            <div><div className="text-muted text-xs">Strategy · Regime</div><b>{latest.strategy}{latest.regime ? ` · ${latest.regime}` : ""}</b></div>
            <div><div className="text-muted text-xs">Signal score</div><b className="num">{Number(latest.score).toFixed(2)}</b></div>
          </div>
          <div className="text-xs text-muted mt-2">{latest.reason}</div>
          <div className="text-xs mt-1">Risk check: <b className={latest.risk_passed === false ? "text-loss" : "text-profit"}>{latest.risk_passed === false ? "REJECTED" : "PASSED"}</b> {latest.risk_reason && <span className="text-muted">· {latest.risk_reason}</span>}</div>
          {latest.sentiment && <div className="text-xs mt-1">News sentiment: <b>{latest.sentiment}</b></div>}
        </Card>
      )}
      <div className="grid md:grid-cols-2 gap-3">
        <Card title="Strategy activity" sub="Signal counts by strategy (live session)">
          <div className="h-64">
            <ResponsiveContainer><BarChart data={data}>
              <XAxis dataKey="strategy" tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#151F30", border: "1px solid #334155" }} />
              <Bar dataKey="buy" fill="#10B981" /><Bar dataKey="sell" fill="#EF4444" />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Card title="Decision history" sub="Newest first">
          {signals.length === 0 ? <Empty msg="No decisions yet." /> : (
            <div className="space-y-2 max-h-72 overflow-auto">
              {signals.slice(0, 30).map((s, i) => (
                <div key={i} className="text-xs border border-bord rounded-lg p-2 flex gap-2 items-center">
                  <b>{s.ticker}</b>
                  <span className={s.action === "BUY" ? "text-profit font-bold" : s.action === "SELL" ? "text-loss font-bold" : "text-muted"}>{s.action}</span>
                  <span className="text-muted">{s.strategy} · {Number(s.score).toFixed(2)} · {s.reason.slice(0, 80)}</span>
                  <span className="ml-auto text-muted">d{s.sim_day}</span>
                </div>))}
            </div>)}
        </Card>
      </div>
    </div>
  );
}
export default function Page() { return <Providers><StratInner /></Providers>; }
