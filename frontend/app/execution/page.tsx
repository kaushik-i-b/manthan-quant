"use client";

import { useMemo, useState } from "react";

import { Empty, Kpi, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatIst, inr } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

export default function ExecutionPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const error = useDesk((state) => state.error);
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  const [day, setDay] = useState("");
  const [q, setQ] = useState("");

  const rows = useMemo(() => {
    return (snapshot?.audit ?? []).filter((row) => {
      const payload = row.payload;
      if (ticker && String(payload.ticker ?? "") !== ticker.toUpperCase()) return false;
      if (action && String(payload.action ?? "") !== action.toUpperCase()) return false;
      if (status && String(payload.status ?? "") !== status.toUpperCase()) return false;
      if (day && String(payload.sim_day ?? "") !== day) return false;
      if (q) {
        const blob = `${payload.ticker ?? ""} ${payload.action ?? ""} ${payload.reason ?? ""} ${payload.message ?? ""}`.toLowerCase();
        if (!blob.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [action, day, q, snapshot, status, ticker]);

  if (!snapshot && !error) return <LoadingBlock label="Loading execution health." />;
  if (!snapshot) return <Empty title="Execution monitor offline" body={error ?? "No health payload yet."} />;
  const health = snapshot.health;
  const orders = snapshot.orders;
  const count = (name: string) => orders.filter((row) => row.status === name).length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Execution monitor</h1>
        <p className="text-sm text-[#94A3B8]">{health.rate_limit.note}</p>
      </div>
      {snapshot.portal ? (
        <Panel title="Portal contracts">
          <p className="text-sm text-[#F59E0B]">
            JSON schemas are unresolved. Bot authentication is {snapshot.portal.bot_auth}. The portal console uses {snapshot.portal.portal_console_auth}.
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-lg bg-[#0B1220] px-3 py-2 text-sm">
              <div className="text-xs text-[#94A3B8]">{snapshot.portal.clock.path}</div>
              <p className="mt-1 text-[#F8FAFC]">
                Local analog day {snapshot.portal.clock.local_simulator.sim_day} of {snapshot.portal.clock.local_simulator.total_days}, {snapshot.portal.clock.local_simulator.remaining_days} remaining, {snapshot.portal.clock.local_simulator.interval_seconds}s interval.
              </p>
              <p className="mt-1 text-xs text-[#94A3B8]">Documented concepts: {snapshot.portal.clock.documented_concepts.join(", ")}. These local numbers are not a portal response.</p>
            </div>
            <div className="rounded-lg bg-[#0B1220] px-3 py-2 text-sm">
              <div className="text-xs text-[#94A3B8]">{snapshot.portal.cash.path}</div>
              <p className="mt-1 text-[#F8FAFC]">Local cash {inr(snapshot.portal.cash.local_simulator_cash)}</p>
              <p className="mt-1 text-xs text-[#94A3B8]">History is {snapshot.portal.history_path}. The cash JSON field name was not printed.</p>
            </div>
          </div>
        </Panel>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Submitted / filled" value={String(count("FILLED"))} hint={`${orders.length} visible order rows`} />
        <Kpi label="Rejected" value={String(count("REJECTED"))} tone={count("REJECTED") ? -1 : 0} />
        <Kpi label="Failed or unknown" value={String(count("FAILED") + count("UNKNOWN"))} tone={count("UNKNOWN") ? -1 : 0} />
        <Kpi label="API latency p50" value={health.decision_latency_ms_p50 == null ? "—" : `${health.decision_latency_ms_p50.toFixed(2)} ms`} hint="Decision time, measured on this process" />
        <Kpi label="Kafka lag" value={health.kafka_lag == null ? "n/a" : String(health.kafka_lag)} hint={health.kafka === "disabled" ? "Kafka is disabled in mock mode" : health.kafka} />
        <Kpi label="Heartbeat" value={health.heartbeat} hint={health.heartbeat_error || `${health.heartbeat_acks} acks`} />
        <Kpi label="Last market event" value={health.last_event_age_sec == null ? "—" : `${health.last_event_age_sec.toFixed(1)}s ago`} />
        <Kpi label="Rate limit" value={`${health.rate_limit.used}/${health.rate_limit.limit}`} hint={`${health.rate_limit.remaining} remaining`} />
      </div>
      <Panel title="Audit" action={<Button size="xs" variant="outline" onClick={() => { setTicker(""); setAction(""); setStatus(""); setDay(""); setQ(""); }}>Clear</Button>}>
        <div className="mb-3 grid gap-2 md:grid-cols-5">
          <Input value={ticker} onChange={(event) => setTicker(event.target.value)} placeholder="Ticker" className="border-[#334155] bg-[#0B1220]" />
          <Input value={action} onChange={(event) => setAction(event.target.value)} placeholder="Action" className="border-[#334155] bg-[#0B1220]" />
          <Input value={status} onChange={(event) => setStatus(event.target.value)} placeholder="Status" className="border-[#334155] bg-[#0B1220]" />
          <Input value={day} onChange={(event) => setDay(event.target.value)} placeholder="Sim day" className="border-[#334155] bg-[#0B1220]" />
          <Input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Search reason" className="border-[#334155] bg-[#0B1220]" />
        </div>
        {rows.length === 0 ? (
          <Empty title="No audit rows match" body="Filters apply to the in-memory audit tape. A rejection includes the risk reason." />
        ) : (
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] tracking-wider text-[#94A3B8] uppercase">
                <tr>
                  <th className="py-2">Time</th>
                  <th>Type</th>
                  <th>Ticker</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 80).map((row, index) => (
                  <tr key={`${row.ts}-${index}`} className="border-t border-[#334155] align-top">
                    <td className="py-2 text-xs text-[#94A3B8]">{formatIst(row.ts)}</td>
                    <td>{row.event_type}</td>
                    <td>{String(row.payload.ticker ?? "—")}</td>
                    <td>{String(row.payload.action ?? "—")}</td>
                    <td className={cn(String(row.payload.status) === "REJECTED" && "text-[#EF4444]")}>{String(row.payload.status ?? "—")}</td>
                    <td className="max-w-md text-xs text-[#94A3B8]">{String(row.payload.rejection_reason ?? row.payload.message ?? row.payload.reason ?? "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
