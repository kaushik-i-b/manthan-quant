"use client";

import type { ReactNode } from "react";
import { cn } from "cn";

import { pnlClass } from "@/lib/format";

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-[#334155] bg-[#151F30] shadow-[0_12px_40px_rgba(0,0,0,0.18)]", className)}>
      <header className="flex items-center justify-between gap-3 border-b border-[#334155] px-4 py-3">
        <h2 className="text-xs font-medium tracking-[0.16em] text-[#94A3B8] uppercase">{title}</h2>
        {action}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: number | null;
}) {
  return (
    <div className="rounded-xl border border-[#334155] bg-[#151F30] px-4 py-3">
      <div className="text-[11px] tracking-[0.14em] text-[#94A3B8] uppercase">{label}</div>
      <div className={cn("num mt-2 text-xl font-medium", tone == null ? "text-[#F8FAFC]" : pnlClass(tone))}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-[#94A3B8]">{hint}</div> : null}
    </div>
  );
}

export function Lamp({ lamp }: { lamp: string }) {
  const color =
    lamp === "LIVE" ? "bg-[#10B981]" : lamp === "PAUSED" ? "bg-[#F59E0B]" : lamp === "PREFLIGHT" ? "bg-[#22D3EE]" : "bg-[#EF4444]";
  return (
    <div className="flex items-center gap-2 rounded-full border border-[#334155] bg-[#1E293B] px-3 py-1.5">
      <span className={cn("size-2.5 rounded-full", color, lamp === "LIVE" && "animate-pulse")} />
      <span className="text-xs font-semibold tracking-[0.18em]">{lamp}</span>
    </div>
  );
}

export function Pill({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="rounded-md border border-[#334155] bg-[#1E293B] px-2.5 py-1">
      <div className="text-[10px] tracking-wider text-[#94A3B8] uppercase">{label}</div>
      <div className={cn("num text-xs", warn ? "text-[#F59E0B]" : "text-[#F8FAFC]")}>{value}</div>
    </div>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[#334155] bg-[#0B1220]/40 px-4 py-8 text-center">
      <div className="text-sm text-[#F8FAFC]">{title}</div>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-[#94A3B8]">{body}</p>
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="space-y-3">
      <div className="h-4 w-40 animate-pulse rounded bg-[#1E293B]" />
      <div className="h-28 animate-pulse rounded-xl bg-[#1E293B]" />
      <p className="text-xs text-[#94A3B8]">{label}</p>
    </div>
  );
}

const MILESTONES: { key: string; label: string }[] = [
  { key: "market_data", label: "Tape" },
  { key: "indicators", label: "Indicators" },
  { key: "signal", label: "Signal" },
  { key: "risk_pass", label: "Risk pass" },
  { key: "fill", label: "Fill" },
  { key: "pnl_updated", label: "P&L" },
  { key: "risk_reject", label: "Risk block" },
  { key: "outage_recovered", label: "Recovered" },
];

export function Milestones({ flags }: { flags: Record<string, boolean> }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
      {MILESTONES.map((item) => {
        const on = Boolean(flags[item.key]);
        return (
          <div key={item.key} className={cn("rounded-lg border px-2 py-2 text-center text-[11px]", on ? "border-[#22D3EE]/50 bg-[#22D3EE]/10 text-[#22D3EE]" : "border-[#334155] text-[#94A3B8]")}>
            {item.label}
          </div>
        );
      })}
    </div>
  );
}
