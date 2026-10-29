"use client";
import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { useLive } from "@/hooks/useLive";
import { useStream } from "@/hooks/useStream";
import { api } from "@/lib/api";
import type { Health, PortfolioSnap, StockRow } from "@/types";

const qc = new QueryClient();

function Shell({ children }: { children: React.ReactNode }) {
  const { ingest, setHealth, setPortfolio, setStocks } = useLive();
  const { connected, stale } = useStream(ingest);
  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const [h, p, s] = await Promise.all([
          api<Health>("/api/health"),
          api<PortfolioSnap>("/api/portfolio"),
          api<StockRow[]>("/api/stocks"),
        ]);
        if (!alive) return;
        setHealth(h); setPortfolio(p); setStocks(s);
      } catch { /* backend starting */ }
    }
    poll();
    const t = setInterval(poll, 3000);
    return () => { alive = false; clearInterval(t); };
  }, [setHealth, setPortfolio, setStocks]);
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 min-w-0">
        <Topbar ws={connected} stale={stale} />
        <main className="p-4 max-w-[1400px] mx-auto">{children}</main>
      </div>
    </div>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={qc}><Shell>{children}</Shell></QueryClientProvider>;
}
