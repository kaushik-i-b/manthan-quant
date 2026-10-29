"use client";

import { Empty, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { formatIst, pct } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

export default function StrategyPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const error = useDesk((state) => state.error);
  if (!snapshot && !error) return <LoadingBlock label="Loading strategy state." />;
  if (!snapshot) return <Empty title="Strategy center offline" body={error ?? "The engine is not publishing decisions."} />;

  const featured = snapshot.decisions.find((row) => row.action !== "HOLD") ?? snapshot.decisions[0];
  const counts = snapshot.orders.reduce<Record<string, number>>((acc, order) => {
    if (order.status === "FILLED") acc[order.strategy] = (acc[order.strategy] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Strategy center</h1>
        <p className="text-sm text-[#94A3B8]">
          Active selector: {snapshot.health.active_strategy}. Last primary: {snapshot.health.last_primary_strategy ?? "—"}. Scores are heuristics.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <Panel title="Decision card">
          {featured ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <div className="text-xs tracking-[0.16em] text-[#94A3B8]">{featured.ticker}</div>
                  <div className="text-3xl font-semibold">{featured.action}</div>
                </div>
                <div className="text-right">
                  <div className="num text-3xl text-[#22D3EE]">{featured.signal_score.toFixed(2)}</div>
                  <div className="text-xs text-[#94A3B8]">{featured.score_type} score</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
                <Fact label="Strategy" value={featured.strategy} />
                <Fact label="Regime" value={featured.regime} />
                <Fact label="Risk" value={featured.risk_approved == null ? "Not sent" : featured.risk_approved ? "Passed" : "Rejected"} />
                <Fact label="RSI" value={num(featured.indicators.rsi14)} />
                <Fact label="EMA9" value={num(featured.indicators.ema9)} />
                <Fact label="News" value={featured.news_label ?? "none"} />
              </div>
              <p className="text-sm leading-6 text-[#94A3B8]">{featured.reason}</p>
              <div className="text-xs text-[#94A3B8]">Day {featured.sim_day} · {formatIst(featured.timestamp)}</div>
              {featured.rejection_reason ? <div className="rounded-lg border border-[#EF4444]/40 bg-[#EF4444]/10 px-3 py-2 text-sm text-[#EF4444]">{featured.rejection_reason}</div> : null}
            </div>
          ) : (
            <Empty title="No decision yet" body="Warmup bars do not create orders. The first live day will." />
          )}
        </Panel>
        <Panel title="Indicator contributions">
          {featured ? (
            <ul className="space-y-3">
              {Object.entries(featured.contributions).map(([name, part]) => (
                <li key={name}>
                  <div className="mb-1 flex justify-between text-xs text-[#94A3B8]">
                    <span>{name}</span>
                    <span className="num">weight {part.weight.toFixed(2)} · score {part.score.toFixed(2)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#0B1220]">
                    <div className="h-full bg-[#22D3EE]" style={{ width: `${Math.min(100, Math.abs(part.weighted) * 100)}%` }} />
                  </div>
                  <div className="mt-1 text-[11px] text-[#94A3B8]">{part.reasons[0]}</div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No contribution breakdown" body="The selector publishes weights with each decision." />
          )}
        </Panel>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {Object.entries(counts).length === 0 ? (
          <Panel title="Strategy fills" className="md:col-span-3">
            <Empty title="No fills attributed yet" body="Filled orders are grouped by the strategy that proposed them." />
          </Panel>
        ) : (
          Object.entries(counts).map(([name, count]) => (
            <div key={name} className="rounded-xl border border-[#334155] bg-[#151F30] px-4 py-3">
              <div className="text-xs tracking-wider text-[#94A3B8] uppercase">{name}</div>
              <div className="num mt-2 text-2xl">{count} fills</div>
            </div>
          ))
        )}
      </div>
      <Panel title="Decision history">
        <div className="overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] tracking-wider text-[#94A3B8] uppercase">
              <tr>
                <th className="py-2">Day</th>
                <th>Ticker</th>
                <th>Action</th>
                <th>Strategy</th>
                <th>Score</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.decisions.slice(0, 20).map((row) => (
                <tr key={row.id} className="border-t border-[#334155]">
                  <td className="num py-2">{row.sim_day}</td>
                  <td>{row.ticker}</td>
                  <td className={cn(row.action === "HOLD" && "text-[#94A3B8]")}>{row.action}</td>
                  <td className="text-[#94A3B8]">{row.strategy}</td>
                  <td className="num">{row.signal_score.toFixed(2)}</td>
                  <td className="text-[#94A3B8]">{row.executed ? "Filled" : row.rejection_reason ? "Rejected" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-[#94A3B8]">Win-rate context lives on the portfolio page. Return {pct(snapshot.portfolio.total_return_pct)} is mark-to-market on this tape only.</p>
      </Panel>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#0B1220] px-3 py-2">
      <div className="text-[10px] tracking-wider text-[#94A3B8] uppercase">{label}</div>
      <div className="mt-1 text-sm">{value}</div>
    </div>
  );
}

function num(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "—";
}
