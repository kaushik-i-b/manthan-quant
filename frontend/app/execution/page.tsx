"use client";
import { useEffect, useState } from "react";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { api } from "@/lib/api";
import type { OrderRow } from "@/types";

function ExInner() {
  const { health, orders } = useLive();
  const [local, setLocal] = useState<OrderRow[]>([]);
  const [f, setF] = useState("");
  useEffect(() => { api<OrderRow[]>("/api/orders").then((o) => { setLocal(o); useLive.getState().setOrders(o); }).catch(() => {}); }, [health?.sim_day]);
  const rows = (orders.length ? orders : local).filter((o) => !f || o.ticker.includes(f.toUpperCase()) || o.status.includes(f.toUpperCase()));
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["API latency", `${health?.api_latency_ms ?? 0} ms`], ["Rate use", `${health?.rate_used ?? 0}/${health?.rate_limit ?? 110}/min`], ["Heartbeat", health?.heartbeat_ok ? "OK" : "FAIL"], ["Decisions", String(health?.decisions ?? 0)], ["Avg decision", `${health?.avg_decision_ms ?? 0} ms`], ["Kafka mode", health?.kafka ?? "…"], ["Stage", health?.stage ?? "…"], ["Uptime", `${health?.uptime_s ?? 0}s`]].map(([k, v]) => (
          <div key={k} className="bg-panel border border-bord rounded-xl p-4"><div className="text-[11px] uppercase tracking-wider text-muted">{k}</div><div className="text-lg font-bold num mt-1">{v}</div></div>))}
      </div>
      <Card title="Order audit" sub="Searchable — filter by ticker or status" right={<input value={f} onChange={(e) => setF(e.target.value)} placeholder="Filter…" className="bg-surface border border-bord rounded-lg px-2 py-1 text-xs outline-none" />}>
        {rows.length === 0 ? <Empty msg="No orders yet." /> : (
          <div className="overflow-auto max-h-[520px]"><table className="w-full text-xs num">
            <thead className="sticky top-0 bg-panel"><tr className="text-muted text-left"><th>Ticker</th><th>Action</th><th>Qty</th><th>Status</th><th>Fill</th><th>Reason</th><th>Day</th></tr></thead>
            <tbody>{rows.slice(0, 100).map((o, i) => (
              <tr key={i} className="border-t border-bord"><td className="py-1.5 font-bold">{o.ticker}</td><td>{o.action}</td><td>{o.quantity ?? "—"}</td>
                <td className={o.status === "CONFIRMED" ? "text-profit" : o.status === "REJECTED" ? "text-warn" : o.status === "FAILED" ? "text-loss" : ""}>{o.status}</td>
                <td>{o.fill_price ?? "—"}</td><td className="text-muted max-w-[280px] truncate">{o.reason ?? ""}</td><td>{o.sim_day}</td></tr>))}
            </tbody>
          </table></div>)}
      </Card>
    </div>
  );
}
export default function Page() { return <Providers><ExInner /></Providers>; }
