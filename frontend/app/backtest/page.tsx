"use client";

import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Empty, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/engine";
import { inr, pct } from "@/lib/format";
import { useDesk } from "@/lib/store";
import type { BacktestReport } from "@/lib/types";

const COLORS: Record<string, string> = {
  adaptive: "#22D3EE",
  buy_hold: "#10B981",
  momentum: "#F59E0B",
  mean_reversion: "#A78BFA",
  cash: "#94A3B8",
};

export default function BacktestPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const [report, setReport] = useState<BacktestReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [focus, setFocus] = useState("adaptive");

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch(apiUrl("/api/backtest/compare"), { method: "POST" });
      if (!response.ok) throw new Error(`Backtest failed (${response.status})`);
      const body = (await response.json()) as BacktestReport;
      setReport(body);
      setFocus("adaptive");
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Backtest failed");
    } finally {
      setRunning(false);
    }
  }

  if (!snapshot && !report) return <LoadingBlock label="The lab runs on the engine. Connecting first." />;

  const curves = report
    ? mergeCurves(report)
    : [];
  const focused = report?.results[focus];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Backtesting lab</h1>
          <p className="max-w-3xl text-sm text-[#94A3B8]">
            Dataset synthetic_demo_v1. The engine replays one day at a time. The entry threshold is chosen on the train window only.
          </p>
        </div>
        <Button disabled={running} onClick={run}>{running ? "Running" : "Run comparison"}</Button>
      </div>
      {error ? <div className="rounded-lg border border-[#EF4444]/40 bg-[#EF4444]/10 px-3 py-2 text-sm text-[#EF4444]">{error}</div> : null}
      {!report ? (
        <Empty title="No backtest yet" body="Run the comparison to score adaptive, buy-and-hold, momentum, mean reversion, and cash on the same synthetic tape." />
      ) : (
        <>
          <div className="rounded-xl border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-4 py-3 text-sm text-[#F59E0B]">
            {report.disclaimer} Elapsed {report.elapsed_ms.toFixed(0)} ms. Seed {report.seed}. Selected threshold {report.selected_entry_threshold}. {report.selection_rule}
          </div>
          <Panel title="Ranking on the full sample (includes the train window)">
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-[11px] tracking-wider text-[#94A3B8] uppercase">
                  <tr>
                    <th className="py-2">Strategy</th>
                    <th>Return</th>
                    <th>Net profit</th>
                    <th>Max DD</th>
                    <th>Sharpe</th>
                    <th>Win rate</th>
                    <th>Trades</th>
                    <th>Costs</th>
                    <th>Rejected</th>
                  </tr>
                </thead>
                <tbody>
                  {report.ranking.map((row) => (
                    <tr key={row.strategy} className="cursor-pointer border-t border-[#334155]" onClick={() => setFocus(row.strategy)}>
                      <td className="py-2" style={{ color: COLORS[row.strategy] ?? "#F8FAFC" }}>{row.strategy}</td>
                      <td className="num">{pct(row.total_return_pct)}</td>
                      <td className="num">{inr(row.net_profit)}</td>
                      <td className="num">{pct(row.max_drawdown_pct)}</td>
                      <td className="num">{row.sharpe == null ? "—" : row.sharpe.toFixed(2)}</td>
                      <td className="num">{row.win_rate == null ? "—" : pct(row.win_rate * 100, 1)}</td>
                      <td className="num">{row.trade_count}</td>
                      <td className="num">{inr(row.transaction_costs)}</td>
                      <td className="num">{row.rejected_orders}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="Equity curves">
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={curves}>
                  <CartesianGrid stroke="#1E293B" vertical={false} />
                  <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                  <YAxis stroke="#94A3B8" fontSize={11} width={72} />
                  <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} />
                  <Legend />
                  {Object.keys(report.results).map((name) => (
                    <Line key={name} type="monotone" dataKey={name} stroke={COLORS[name] ?? "#F8FAFC"} dot={false} strokeWidth={name === focus ? 2.4 : 1.2} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title={`${focus} drawdown`}>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={focused?.equity ?? []}>
                    <CartesianGrid stroke="#1E293B" vertical={false} />
                    <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                    <YAxis stroke="#94A3B8" fontSize={11} tickFormatter={(value) => `${(Number(value) * 100).toFixed(1)}%`} />
                    <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} />
                    <Line dataKey="drawdown" stroke="#EF4444" dot={false} name="Drawdown" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="Walk-forward adaptive">
              <ul className="space-y-2 text-sm">
                <li className="flex justify-between"><span>Train {report.splits.train.join("–")}</span><span className="num">{pct(report.train.find((row) => row.entry_threshold === report.selected_entry_threshold)?.total_return_pct)}</span></li>
                <li className="flex justify-between"><span>Validation {report.splits.validation.join("–")}</span><span className="num">{pct(report.validation.total_return_pct)}</span></li>
                <li className="flex justify-between"><span>Test {report.splits.test.join("–")}</span><span className="num">{pct(report.test.total_return_pct)}</span></li>
                <li className="text-xs leading-5 text-[#94A3B8]">{report.test.sharpe_note}</li>
                <li className="text-xs text-[#94A3B8]">Test costs {inr(report.test.transaction_costs)}. Test trades {report.test.trade_count}. Decision p50 {report.test.decision_latency_ms_p50 == null ? "—" : `${report.test.decision_latency_ms_p50.toFixed(2)} ms`}.</li>
              </ul>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function mergeCurves(report: BacktestReport) {
  const days = new Map<number, Record<string, number>>();
  for (const [name, row] of Object.entries(report.results)) {
    for (const point of row.equity ?? []) {
      const entry = days.get(point.sim_day) ?? { sim_day: point.sim_day };
      entry[name] = point.equity;
      days.set(point.sim_day, entry);
    }
  }
  return [...days.values()].sort((a, b) => a.sim_day - b.sim_day);
}
