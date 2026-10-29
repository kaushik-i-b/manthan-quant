"use client";
import { useEffect, useState } from "react";
import { Providers } from "./providers";
import { Card, Kpi, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { api, fmtINR, pct } from "@/lib/api";
import type { OrderRow, PortfolioSnap, SignalItem } from "@/types";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from "recharts";

function OverviewInner() {
  const { portfolio, health, signals, stocks } = useLive();
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [curve, setCurve] = useState<{ sim_day: number; equity: number }[]>([]);
  useEffect(() => {
    api<PortfolioSnap>("/api/portfolio").then((p) => {
      useLive.getState().setPortfolio(p);
    }).catch(() => {});
    api<OrderRow[]>("/api/orders").then(setOrders).catch(() => {});
    api<SignalItem[]>("/api/signals?n=20").then((s) => useLive.getState().setSignals(s)).catch(() => {});
  }, [health?.sim_day]);
  useEffect(() => {
    if (portfolio) setCurve((c) => [...c.slice(-200), { sim_day: portfolio.sim_day, equity: portfolio.equity }]);
  }, [portfolio?.sim_day]);

  if (!portfolio) return <Empty msg="Connecting to trading engine…" />;
  const p = portfolio;
  const alloc = Object.entries(p.positions).filter(([, v]) => v.qty > 0)
    .map(([k, v]) => ({ name: k, value: Math.round(v.qty * v.avg_price) }));
  const cashSlice = [{ name: "Cash", value: Math.round(p.cash) }, ...alloc];
  const COLORS = ["#22D3EE", "#10B981", "#F59E0B", "#818CF8", "#F472B6", "#94A3B8"];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Portfolio value" value={fmtINR(p.equity)} delta={pct(p.total_return_pct)} tone={p.total_return_pct >= 0 ? "up" : "down"} />
        <Kpi label="Total P&L" value={fmtINR(p.realized_pnl + p.unrealized_pnl)} tone={(p.realized_pnl + p.unrealized_pnl) >= 0 ? "up" : "down"} />
        <Kpi label="Cash" value={fmtINR(p.cash)} />
        <Kpi label="Invested" value={fmtINR(p.invested)} />
        <Kpi label="Drawdown" value={pct(-p.drawdown_pct)} tone={p.drawdown_pct > 5 ? "down" : "flat"} />
        <Kpi label="Return" value={pct(p.total_return_pct)} tone={p.total_return_pct >= 0 ? "up" : "down"} />
        <Kpi label="Trades" value={String(orders.length)} />
        <Kpi label="Sim day" value={String(p.sim_day)} />
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        <Card title="Equity curve" sub="Live portfolio equity per simulated day" className="md:col-span-2">
          <div className="h-64">
            <ResponsiveContainer>
              <AreaChart data={curve}>
                <XAxis dataKey="sim_day" tick={{ fill: "#94A3B8", fontSize: 11 }} />
                <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#151F30", border: "1px solid #334155" }} />
                <Area type="monotone" dataKey="equity" stroke="#22D3EE" fill="#22D3EE33" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Allocation" sub="Cash vs invested">
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={cashSlice.length ? cashSlice : [{ name: "Cash", value: 1 }]} dataKey="value" nameKey="name" outerRadius={90}>
                  {cashSlice.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#151F30", border: "1px solid #334155" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        <Card title="Recent orders" sub="Latest execution results">
          {orders.length === 0 ? <Empty msg="No orders yet — engine is observing the market." /> : (
            <table className="w-full text-xs num">
              <thead><tr className="text-muted text-left"><th>Ticker</th><th>Action</th><th>Qty</th><th>Status</th><th>Day</th></tr></thead>
              <tbody>{orders.slice(0, 8).map((o, i) => (
                <tr key={i} className="border-t border-bord"><td className="py-1.5 font-semibold">{o.ticker}</td>
                  <td className={o.action === "BUY" ? "text-profit" : o.action === "SELL" ? "text-loss" : "text-warn"}>{o.action}</td>
                  <td>{o.quantity ?? "—"}</td><td>{o.status}</td><td>{o.sim_day}</td></tr>))}
              </tbody>
            </table>)}
        </Card>
        <Card title="Live strategy decisions" sub="Explainable signals from the engine">
          {signals.length === 0 ? <Empty msg="Waiting for first signals…" /> : (
            <div className="space-y-2 max-h-72 overflow-auto">
              {signals.slice(0, 8).map((s, i) => (
                <div key={i} className="border border-bord rounded-lg p-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <b>{s.ticker}</b>
                    <span className={`px-2 py-0.5 rounded-full font-bold ${s.action === "BUY" ? "bg-profit/15 text-profit" : s.action === "SELL" ? "bg-loss/15 text-loss" : "bg-surface text-muted"}`}>{s.action}</span>
                    <span className="text-muted ml-auto">{s.strategy} · {Number(s.score).toFixed(2)} · day {s.sim_day}</span>
                  </div>
                  <div className="text-muted mt-1">{s.reason}{s.risk_reason ? ` · Risk: ${s.risk_reason}` : ""}</div>
                </div>))}
            </div>)}
        </Card>
      </div>
    </div>
  );
}

export default function Page() {
  return <Providers><OverviewInner /></Providers>;
}
