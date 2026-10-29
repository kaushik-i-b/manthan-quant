"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  Brain,
  CandlestickChart,
  FlaskConical,
  LayoutDashboard,
  ShieldAlert,
  Wallet,
} from "lucide-react";

import { Lamp, Pill } from "@/components/terminal/widgets";
import { useDeskConnection } from "@/hooks/use-desk";
import { nowIst } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/market", label: "Market", icon: CandlestickChart },
  { href: "/strategy", label: "Strategy", icon: Brain },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/execution", label: "Execution", icon: Activity },
  { href: "/risk", label: "Risk", icon: ShieldAlert },
  { href: "/backtest", label: "Backtest", icon: FlaskConical },
];

export function Shell({ children }: { children: React.ReactNode }) {
  useDeskConnection();
  const pathname = usePathname();
  const snapshot = useDesk((state) => state.snapshot);
  const status = useDesk((state) => state.status);
  const error = useDesk((state) => state.error);
  const [clock, setClock] = useState("--:--:-- IST");

  useEffect(() => {
    const tick = () => setClock(nowIst());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const health = snapshot?.health;
  const synthetic = snapshot?.meta.data_origin === "synthetic";

  return (
    <div className="min-h-screen bg-[#0B1220] text-[#F8FAFC]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-[#334155] bg-[#0B1220] md:flex">
        <div className="border-b border-[#334155] px-4 py-5">
          <div className="text-[11px] tracking-[0.22em] text-[#22D3EE]">MANTHAN 2026</div>
          <div className="mt-1 text-lg font-semibold tracking-tight">MANTHAN QUANT</div>
          <div className="text-xs text-[#94A3B8]">Simulation desk</div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#94A3B8] hover:bg-[#1E293B] hover:text-[#F8FAFC]",
                  active && "bg-[#1E293B] text-[#F8FAFC]",
                )}
              >
                <Icon className={cn("size-4", active && "text-[#22D3EE]")} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-[#334155] px-4 py-3 text-[11px] leading-5 text-[#94A3B8]">
          Orders leave this browser only as local control commands. The venue token stays on the engine.
        </div>
      </aside>

      <div className="md:pl-56">
        <header className="sticky top-0 z-20 border-b border-[#334155] bg-[#0B1220]/95 backdrop-blur">
          <div className="flex items-center gap-2 overflow-x-auto px-3 py-2 md:hidden">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={cn("rounded-md px-2 py-1 text-xs text-[#94A3B8]", pathname === item.href && "bg-[#1E293B] text-[#F8FAFC]")}>
                {item.label}
              </Link>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 px-4 py-3">
            <Lamp lamp={health?.lamp ?? (status === "connecting" ? "LINKING" : "OFFLINE")} />
            <Pill label="Feed" value={status === "error" ? "error" : health?.feed ?? status} warn={health?.feed === "interrupted" || status === "stale" || status === "disconnected"} />
            <Pill label="Kafka" value={health?.kafka ?? "—"} warn={health?.kafka === "disconnected"} />
            <Pill label="API" value={health?.trading_api ?? "—"} warn={health?.trading_api === "unreachable"} />
            <Pill label="Heartbeat" value={health ? `${health.heartbeat} · ${health.heartbeat_acks}` : "—"} warn={health?.heartbeat === "failing"} />
            <Pill label="Stage" value={health?.stage ?? "—"} />
            <Pill label="Sim day" value={health ? String(health.sim_day) : "—"} />
            <Pill label="Strategy" value={health?.active_strategy ?? "—"} />
            <Pill label="Mode" value={health?.mode ?? "—"} warn={health?.mode === "LIVE_SIMULATION"} />
            <div className="ml-auto text-xs text-[#94A3B8]">{clock}</div>
          </div>
          {synthetic ? (
            <div className="border-t border-[#F59E0B]/30 bg-[#F59E0B]/10 px-4 py-2 text-xs text-[#F59E0B]">
              Synthetic demonstration tape. Figures are produced by the local mock exchange and are not competition results.
              {snapshot?.meta.cost_model ? ` Cost model: ${snapshot.meta.cost_model} (not an official schedule).` : ""}
            </div>
          ) : null}
          {error && !snapshot ? (
            <div className="border-t border-[#EF4444]/40 bg-[#EF4444]/10 px-4 py-2 text-xs text-[#EF4444]">
              Desk cannot reach the engine: {error}
            </div>
          ) : null}
        </header>
        <main className="px-4 py-4 md:px-6 md:py-6">{children}</main>
      </div>
    </div>
  );
}
