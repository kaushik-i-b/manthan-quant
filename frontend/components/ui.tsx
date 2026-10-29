"use client";
import { ReactNode } from "react";

export function Card({ title, sub, right, children, className = "" }: { title?: string; sub?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`bg-panel border border-bord rounded-xl p-4 shadow-sm ${className}`}>
      {(title || right) && (
        <div className="flex items-start justify-between mb-3">
          <div>
            {title && <div className="font-semibold text-ink text-sm">{title}</div>}
            {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, delta, tone = "flat" }: { label: string; value: string; delta?: string; tone?: "up" | "down" | "flat" }) {
  const c = tone === "up" ? "text-profit" : tone === "down" ? "text-loss" : "text-ink";
  return (
    <div className="bg-panel border border-bord rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`text-xl font-bold mt-1 ${c}`}>{value}</div>
      {delta && <div className={`text-xs mt-0.5 ${c}`}>{delta}</div>}
    </div>
  );
}

export function Empty({ msg }: { msg: string }) {
  return <div className="text-sm text-muted py-8 text-center">{msg}</div>;
}
