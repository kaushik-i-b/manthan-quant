"use client";

import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Empty, Kpi, LoadingBlock, Milestones, Panel } from "@/components/terminal/widgets";
import { inr, pct, pnlClass } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

const PIE = ["#22D3EE", "#10B981", "#F59E0B", "#94A3B8", "#EF4444", "#818CF8", "#F8FAFC", "#38BDF8", "#334155"];

export default function OverviewPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const status = useDesk((state) => state.status);
  const error = useDesk((state) => state.error);

  if (!snapshot && !error) return <LoadingBlock label="Waiting for the engine snapshot." />;
  if (!snapshot) return <Empty title="Engine offline" body={error ?? "Start the backend and refresh the desk."} />;

  const book = snapshot.portfolio;
  const allocation = [
    { name: "Cash", value: Math.max(book.available_cash, 0) },
    ...book.holdings.map((row) => ({ name: row.ticker, value: Math.abs(row.market_value) })),
  ].filter((row) => row.value > 0);
  const decisions = snapshot.decisions.slice(0, 6);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm text-[#94A3B8]">Equity, cash, and the decisions the book actually made.</p>
        </div>
        <div className="text-xs text-[#94A3B8]">Valuation: {book.valuation}</div>
      </div>
      <Milestones flags={snapshot.milestones} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Portfolio value" value={inr(book.equity)} hint={`Started ${inr(book.starting_capital)}`} />
        <Kpi label="Total return" value={pct(book.total_return_pct)} tone={book.total_return_pct} />
        <Kpi label="Net P&L" value={inr(book.net_pnl)} tone={book.net_pnl} hint={`Unrealized ${inr(book.unrealized_pnl)}`} />
        <Kpi label="Available cash" value={inr(book.available_cash)} hint={`Locked collateral ${inr(book.locked_collateral)}`} />
        <Kpi label="Invested" value={inr(book.invested)} hint={`Gross exposure ${inr(book.gross_exposure)}`} />
        <Kpi label="Max drawdown" value={pct(book.max_drawdown_pct)} tone={book.max_drawdown_pct > 0 ? -1 : 0} />
        <Kpi label="Fills" value={String(book.fills)} hint={`${book.closed_trades} closed round trips`} />
        <Kpi label="Win rate" value={book.win_rate == null ? "—" : pct(book.win_rate, 1)} hint={book.closed_trades === 0 ? "No closed round trips yet" : `${book.wins} wins · ${book.losses} losses`} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Equity" className="xl:col-span-2">
          {book.equity_history.length < 2 ? (
            <Empty title="Equity is still flat" body="The curve appears after the tape records more than one simulated day." />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={book.equity_history}>
                  <CartesianGrid stroke="#1E293B" vertical={false} />
                  <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                  <YAxis stroke="#94A3B8" fontSize={11} width={80} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}k`} />
                  <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                  <Area type="monotone" dataKey="equity" stroke="#22D3EE" fill="#22D3EE22" name="Equity" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
        <Panel title="Allocation">
          {allocation.length === 0 ? (
            <Empty title="Nothing allocated" body="Cash is the whole book until the first fill." />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={allocation} dataKey="value" nameKey="name" innerRadius={58} outerRadius={86} stroke="#0B1220">
                    {allocation.map((row, index) => (
                      <Cell key={row.name} fill={PIE[index % PIE.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Cash versus invested">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={book.equity_history}>
                <CartesianGrid stroke="#1E293B" vertical={false} />
                <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} width={72} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}k`} />
                <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                <Area type="monotone" dataKey="cash" stroke="#94A3B8" fill="#94A3B822" name="Cash" />
                <Area type="monotone" dataKey="invested" stroke="#F59E0B" fill="#F59E0B22" name="Invested" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="P&L by simulated day">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={book.equity_history}>
                <CartesianGrid stroke="#1E293B" vertical={false} />
                <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} width={72} />
                <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                <Area type="monotone" dataKey="pnl" stroke="#10B981" fill="#10B98122" name="Net P&L" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Recent orders">
          {snapshot.orders.length === 0 ? (
            <Empty title="No orders yet" body="Fills and rejections will show here once the tape leaves warmup." />
          ) : (
            <ul className="space-y-2">
              {snapshot.orders.slice(0, 6).map((order) => (
                <li key={order.client_order_id} className="flex items-center justify-between gap-3 rounded-lg bg-[#0B1220] px-3 py-2 text-sm">
                  <div>
                    <span className="num">{order.ticker}</span>
                    <span className="ml-2 text-[#94A3B8]">{order.action}</span>
                    <span className="ml-2 text-xs text-[#94A3B8]">day {order.sim_day}</span>
                  </div>
                  <span className={cn("text-xs", order.status === "FILLED" ? "text-[#10B981]" : order.status === "REJECTED" ? "text-[#EF4444]" : "text-[#F59E0B]")}>{order.status}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Live decisions">
          {decisions.length === 0 ? (
            <Empty title="No scored decisions yet" body="The selector records a reason for every hold, buy, sell, short, and cover." />
          ) : (
            <ul className="space-y-2">
              {decisions.map((decision) => (
                <li key={decision.id} className="rounded-lg bg-[#0B1220] px-3 py-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>
                      <span className="num">{decision.ticker}</span>
                      <span className={cn("ml-2", pnlClass(decision.action === "BUY" || decision.action === "COVER" ? 1 : decision.action === "HOLD" ? 0 : -1))}>{decision.action}</span>
                    </span>
                    <span className="num text-xs text-[#94A3B8]">{decision.signal_score.toFixed(2)} heuristic</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#94A3B8]">{decision.reason}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <p className="text-[11px] text-[#94A3B8]">Link status: {status}. Scores are heuristics, not probabilities.</p>
    </div>
  );
}
