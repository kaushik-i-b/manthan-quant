"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, CandlestickChart, BrainCircuit, Briefcase, TerminalSquare, ShieldAlert, FlaskConical, LayoutDashboard } from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/market", label: "Market Terminal", icon: CandlestickChart },
  { href: "/strategy", label: "AI Strategy", icon: BrainCircuit },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/execution", label: "Execution", icon: TerminalSquare },
  { href: "/risk", label: "Risk Center", icon: ShieldAlert },
  { href: "/backtest", label: "Backtest Lab", icon: FlaskConical },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col bg-panel border-r border-bord min-h-screen">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-bord">
        <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center">
          <Activity className="w-5 h-5 text-accent" />
        </div>
        <div>
          <div className="font-bold tracking-wide text-ink">MANTHAN QUANT</div>
          <div className="text-[11px] text-muted tracking-widest">AUTONOMOUS TRADING</div>
        </div>
      </div>
      <nav className="p-3 space-y-1 flex-1">
        {NAV.map((n) => {
          const active = path === n.href;
          const Icon = n.icon;
          return (
            <Link key={n.href} href={n.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${active ? "bg-surface text-ink border border-bord" : "text-muted hover:text-ink hover:bg-surface/60"}`}>
              <Icon className={`w-4 h-4 ${active ? "text-accent" : ""}`} />
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 text-[11px] text-muted border-t border-bord">
        Venue: 192.168.65.157 · Mock mode default · DRY_RUN
      </div>
    </aside>
  );
}
