"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { api, fmt2 } from "@/lib/api";

function CandleChart({ ticker }: { ticker: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<{ remove: () => void } | null>(null);
  const seriesRef = useRef<{ setData: (d: unknown[]) => void; update: (d: unknown) => void } | null>(null);
  useEffect(() => {
    let dead = false;
    (async () => {
      const bars = await api<{ open: number; high: number; low: number; close: number; sim_day: number }[]>(`/api/stocks/${ticker}/history?n=120`);
      if (dead || !ref.current) return;
      const { createChart } = await import("lightweight-charts");
      chartRef.current?.remove();
      const chart = createChart(ref.current, {
        layout: { background: { color: "transparent" }, textColor: "#94A3B8" },
        grid: { vertLines: { color: "#1E293B" }, horzLines: { color: "#1E293B" } },
        height: 380,
      });
      const series = (chart as unknown as { addCandlestickSeries: (o: object) => { setData: (d: unknown[]) => void } }).addCandlestickSeries({
        upColor: "#10B981", downColor: "#EF4444", wickUpColor: "#10B981", wickDownColor: "#EF4444", borderVisible: false,
      });
      series.setData(bars.map((b) => ({ time: String(20240101 + b.sim_day), open: b.open, high: b.high, low: b.low, close: b.close })));
      chart.timeScale().scrollToRealTime();
      seriesRef.current = series as unknown as { setData: (d: unknown[]) => void; update: (d: unknown) => void };
      chartRef.current = chart as unknown as { remove: () => void };
    })();
    return () => { dead = true; };
  }, [ticker]);
  return <div ref={ref} className="w-full" />;
}

function MarketInner() {
  const { stocks, signals } = useLive();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState("RELIANCE");
  const list = useMemo(() => stocks.filter((s) => s.ticker.includes(q.toUpperCase())), [stocks, q]);
  const cur = stocks.find((s) => s.ticker === sel);
  const sig = [...signals].reverse().find((s) => s.ticker === sel);
  const ind = cur?.indicators ?? {};
  return (
    <div className="grid lg:grid-cols-[240px_1fr_280px] gap-3">
      <Card title="Watchlist" sub={`${stocks.length} symbols`}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="w-full mb-2 bg-surface border border-bord rounded-lg px-2 py-1.5 text-sm outline-none" />
        <div className="space-y-1 max-h-[560px] overflow-auto">
          {list.map((s) => (
            <button key={s.ticker} onClick={() => setSel(s.ticker)}
              className={`w-full text-left px-2.5 py-2 rounded-lg border text-xs ${sel === s.ticker ? "border-accent/50 bg-surface" : "border-transparent hover:bg-surface/60"}`}>
              <div className="flex justify-between"><b>{s.ticker}</b><span className="num">₹{fmt2(s.price)}</span></div>
              <div className="text-muted flex justify-between mt-0.5">
                <span>RSI {s.indicators?.rsi14 != null ? Number(s.indicators.rsi14).toFixed(0) : "—"}</span>
                <span>{(s.indicators?.trend_strength as number) === 1 ? "▲ Bull" : (s.indicators?.trend_strength as number) === -1 ? "▼ Bear" : "– Flat"}</span>
              </div>
            </button>))}
          {list.length === 0 && <Empty msg="No symbols match." />}
        </div>
      </Card>
      <Card title={`${sel} · Candles + volume`} sub="TradingView Lightweight Charts · live via WebSocket snapshots">
        <CandleChart key={sel} ticker={sel} />
        <div className="text-[11px] text-muted mt-2">History endpoint: GET /api/stocks/{sel}/history · chart recreates per ticker switch; live ticks stream through the socket.</div>
      </Card>
      <div className="space-y-3">
        <Card title="Signal" sub="Current strategy view">
          {!sig ? <Empty msg="No signal yet for this ticker." /> : (
            <div className="text-xs space-y-1.5">
              <div className="flex items-center gap-2"><b className="text-sm">{sig.ticker}</b>
                <span className={`px-2 py-0.5 rounded-full font-bold ${sig.action === "BUY" ? "bg-profit/15 text-profit" : sig.action === "SELL" ? "bg-loss/15 text-loss" : "bg-surface text-muted"}`}>{sig.action}</span></div>
              <div>Strategy <b>{sig.strategy}</b> · Score <b className="num">{Number(sig.score).toFixed(2)}</b></div>
              <div className="text-muted">{sig.reason}</div>
              {sig.sentiment && <div>News sentiment: <b>{sig.sentiment}</b></div>}
              {sig.risk_reason && <div>Risk: <b>{sig.risk_reason}</b></div>}
            </div>)}
        </Card>
        <Card title="Indicators" sub="Incremental engine snapshot">
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs num">
            {[["EMA9", ind.ema9], ["EMA21", ind.ema21], ["EMA50", ind.ema50], ["RSI14", ind.rsi14], ["MACD", ind.macd], ["ATR14", ind.atr14], ["BB up", ind.bb_upper], ["BB low", ind.bb_lower], ["Vol", ind.volatility]].map(([k, v]) => (
              <div key={k as string} className="flex justify-between border-b border-bord/50 py-1"><span className="text-muted">{k}</span><b>{v != null ? fmt2(Number(v)) : "—"}</b></div>))}
          </div>
        </Card>
        <Card title="News" sub="Latest corporate event">
          {!cur?.news ? <Empty msg="No news for this ticker yet." /> : (
            <div className="text-xs"><div className="font-semibold">{cur.news.headline}</div>
              <div className="text-muted mt-1">Sentiment <b className={cur.news.sentiment === "positive" ? "text-profit" : cur.news.sentiment === "negative" ? "text-loss" : ""}>{cur.news.sentiment}</b> · severity {cur.news.severity}</div></div>)}
        </Card>
      </div>
    </div>
  );
}
export default function Page() { return <Providers><MarketInner /></Providers>; }
