"use client";

import { useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

import { CandleChart } from "@/components/terminal/candle-chart";
import { Empty, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { compact, inr, pct, pnlClass } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

export default function MarketPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const candles = useDesk((state) => state.candles);
  const selected = useDesk((state) => state.selected);
  const setSelected = useDesk((state) => state.setSelected);
  const error = useDesk((state) => state.error);
  const [query, setQuery] = useState("");
  const [overlay, setOverlay] = useState<"none" | "rsi" | "macd">("none");

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (snapshot?.tickers ?? []).filter((row) => !needle || row.ticker.toLowerCase().includes(needle) || row.name.toLowerCase().includes(needle));
  }, [query, snapshot]);

  if (!snapshot && !error) return <LoadingBlock label="Loading the synthetic tape." />;
  if (!snapshot) return <Empty title="No market data" body={error ?? "The engine has not published a universe."} />;

  const ticker = selected ?? snapshot.tickers[0]?.ticker;
  const series = ticker ? candles[ticker] ?? [] : [];
  const quote = snapshot.tickers.find((row) => row.ticker === ticker);
  const decision = snapshot.decisions.find((row) => row.ticker === ticker);
  const news = snapshot.news.filter((item) => item.ticker === ticker).slice(0, 4);
  const last = series[series.length - 1];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Market terminal</h1>
        <p className="text-sm text-[#94A3B8]">Symbols come from the engine universe. This desk does not hardcode a watchlist.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_300px]">
        <Panel title="Watchlist" action={<span className="text-[11px] text-[#94A3B8]">{rows.length}</span>}>
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search ticker" className="mb-3 border-[#334155] bg-[#0B1220]" />
          <div className="max-h-[640px] space-y-1 overflow-auto">
            {rows.length === 0 ? <Empty title="No match" body="Try another ticker from the synthetic universe." /> : null}
            {rows.map((row) => (
              <button
                key={row.ticker}
                type="button"
                onClick={() => setSelected(row.ticker)}
                className={cn("w-full rounded-lg px-2 py-2 text-left hover:bg-[#1E293B]", row.ticker === ticker && "bg-[#1E293B]")}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm">{row.ticker}</span>
                  <span className={cn("num text-sm", pnlClass(row.change))}>{inr(row.last)}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-[#94A3B8]">
                  <span>{row.trend}</span>
                  <span className={pnlClass(row.change)}>{pct(row.change_pct)}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px]">
                  <span className="text-[#94A3B8]">{compact(row.volume)} vol</span>
                  <span className={row.signal === "HOLD" ? "text-[#94A3B8]" : "text-[#22D3EE]"}>{row.signal}</span>
                </div>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title={ticker ? `${ticker} candle` : "Chart"}
          action={
            <div className="flex gap-1">
              {(["none", "rsi", "macd"] as const).map((item) => (
                <Button key={item} size="xs" variant={overlay === item ? "default" : "outline"} onClick={() => setOverlay(item)}>
                  {item.toUpperCase()}
                </Button>
              ))}
            </div>
          }
        >
          {ticker && series.length > 0 ? (
            <CandleChart candles={series} ticker={ticker} origin={snapshot.meta.time_origin_unix} />
          ) : (
            <Empty title="Waiting for bars" body="The chart fills when the engine publishes candles for the selected ticker." />
          )}
          <div className="mt-2 flex gap-3 text-[11px] text-[#94A3B8]">
            <span className="text-[#22D3EE]">EMA 9</span>
            <span className="text-[#F59E0B]">EMA 21</span>
            <span className="text-[#A78BFA]">EMA 50</span>
            <span>Volume</span>
          </div>
          {overlay !== "none" && series.length > 0 ? (
            <div className="mt-3 h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series}>
                  <YAxis hide domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} />
                  <Area type="monotone" dataKey={overlay === "rsi" ? "rsi14" : "macd_hist"} stroke={overlay === "rsi" ? "#22D3EE" : "#F59E0B"} fill="#22D3EE22" name={overlay.toUpperCase()} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </Panel>
        <div className="space-y-4">
          <Panel title="Ticker">
            {quote ? (
              <div className="space-y-2 text-sm">
                <div className="text-[#94A3B8]">{quote.name}{quote.synthetic ? " · synthetic" : ""}</div>
                <div className={cn("num text-2xl", pnlClass(quote.change))}>{inr(quote.last)}</div>
                <div className={cn("num text-sm", pnlClass(quote.change))}>{pct(quote.change_pct)} · {quote.trend}</div>
                <div className="text-xs text-[#94A3B8]">Regime {quote.regime} · score {quote.signal_score.toFixed(2)}</div>
              </div>
            ) : (
              <Empty title="No selection" body="Choose a symbol from the watchlist." />
            )}
          </Panel>
          <Panel title="News">
            {news.length === 0 ? (
              <Empty title="No headline on this name" body="Corporate news is attached to the synthetic tape and scored locally." />
            ) : (
              <ul className="space-y-3">
                {news.map((item) => (
                  <li key={item.event_id}>
                    <div className="text-xs text-[#94A3B8]">Day {item.sim_day} · {item.label} · {item.source}</div>
                    <p className="mt-1 text-sm leading-5">{item.headline}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Why this name">
            {decision ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span>{decision.action}</span><span className="num text-[#22D3EE]">{decision.signal_score.toFixed(2)}</span></div>
                <div className="text-xs text-[#94A3B8]">{decision.strategy} · {decision.regime}</div>
                <p className="text-xs leading-5 text-[#94A3B8]">{decision.reason}</p>
                {last ? (
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-[#94A3B8]">
                    <span>RSI {last.rsi14 ?? "—"}</span>
                    <span>EMA9 {last.ema9?.toFixed(2) ?? "—"}</span>
                    <span>MACD {last.macd?.toFixed(3) ?? "—"}</span>
                    <span>Day {last.sim_day}</span>
                  </div>
                ) : null}
              </div>
            ) : (
              <Empty title="No decision on this ticker" body="A reason appears after the first evaluation." />
            )}
          </Panel>
        </div>
      </div>
      <Panel title="Event tape">
        <div className="grid gap-2 md:grid-cols-3">
          {snapshot.audit.slice(0, 9).map((row, index) => (
            <div key={`${row.ts}-${index}`} className="rounded-lg bg-[#0B1220] px-3 py-2 text-xs">
              <div className="text-[#22D3EE]">{row.event_type}</div>
              <div className="mt-1 text-[#94A3B8]">{String(row.payload.ticker ?? "")} {String(row.payload.action ?? "")}</div>
            </div>
          ))}
          {snapshot.audit.length === 0 ? <Empty title="Tape is quiet" body="Orders and decisions land here as the simulated day advances." /> : null}
        </div>
      </Panel>
    </div>
  );
}
