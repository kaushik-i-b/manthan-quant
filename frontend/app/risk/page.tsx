"use client";

import { useState } from "react";

import { Empty, Kpi, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { Button } from "@/components/ui/button";
import { pct } from "@/lib/format";
import { useDesk } from "@/lib/store";

export default function RiskPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const error = useDesk((state) => state.error);
  const [ack, setAck] = useState<string>("");
  const [pending, setPending] = useState<string>("");

  async function command(path: string, body?: unknown) {
    setPending(path);
    setAck("");
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json();
      if (!response.ok || payload.ack !== true) {
        setAck(`Command was not acknowledged (${response.status}).`);
        return;
      }
      setAck(`${path} acknowledged. Lamp ${payload.lamp ?? "updated"}. Paused: ${String(payload.paused ?? payload.started ?? false)}.`);
    } catch (commandError) {
      setAck(commandError instanceof Error ? commandError.message : "Control request failed");
    } finally {
      setPending("");
    }
  }

  if (!snapshot && !error) return <LoadingBlock label="Loading risk state." />;
  if (!snapshot) return <Empty title="Risk center offline" body={error ?? "No risk model yet."} />;
  const risk = snapshot.risk;
  const tone = risk.health === "healthy" ? "text-[#10B981]" : risk.health === "caution" ? "text-[#F59E0B]" : "text-[#EF4444]";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Risk center</h1>
          <p className={tone}>Health: {risk.health}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={pending !== ""} onClick={() => command("/api/control/pause")}>Pause trading</Button>
          <Button variant="outline" disabled={pending !== ""} onClick={() => command("/api/control/resume")}>Resume</Button>
          <Button variant="outline" disabled={pending !== ""} onClick={() => command("/api/control/outage", { seconds: 6 })}>Simulate feed outage</Button>
        </div>
      </div>
      {ack ? <div className="rounded-lg border border-[#334155] bg-[#1E293B] px-3 py-2 text-sm">{ack}</div> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Drawdown" value={pct(risk.drawdown_pct)} tone={risk.drawdown_pct > 0 ? -risk.drawdown_pct : 0} hint={`Limit ${pct(risk.max_allowed_drawdown_pct)}`} />
        <Kpi label="Observed max" value={pct(risk.max_observed_drawdown_pct)} />
        <Kpi label="Gross exposure" value={pct(risk.exposure_pct)} hint={`Cash reserve ${pct(risk.cash_reserve_pct)} / min ${pct(risk.min_cash_reserve_pct)}`} />
        <Kpi label="Largest position" value={risk.largest_position ? `${risk.largest_position.ticker} ${pct(risk.largest_position.exposure_pct, 1)}` : "—"} hint={risk.largest_position?.side ?? "flat"} />
        <Kpi label="Short exposure" value={`₹${Math.round(risk.short_exposure).toLocaleString("en-IN")}`} />
        <Kpi label="Orders today" value={`${risk.limits.orders_today}/${risk.limits.max_orders_per_day}`} />
        <Kpi label="Position cap" value={pct(risk.limits.max_position_pct * 100)} hint={`Invested cap ${pct(risk.limits.max_invested_pct * 100)}`} />
        <Kpi label="Paused" value={risk.paused ? "Yes" : "No"} tone={risk.paused ? -1 : 1} />
      </div>
      <Panel title="Rejected signals">
        {risk.recent_rejections.length === 0 ? (
          <Empty title="No rejections in the tape" body="The day-78 probe, and any live rule breach, show the exact reason the order was blocked." />
        ) : (
          <ul className="space-y-3">
            {risk.recent_rejections.map((row) => (
              <li key={row.id} className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/5 px-3 py-2">
                <div className="text-sm">{row.ticker} {row.action} · day {row.sim_day} · {row.strategy}</div>
                <p className="mt-1 text-xs leading-5 text-[#94A3B8]">{row.rejection_reason || row.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
