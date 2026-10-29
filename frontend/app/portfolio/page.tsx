"use client";

import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Empty, LoadingBlock, Panel } from "@/components/terminal/widgets";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { inr, pct, pnlClass } from "@/lib/format";
import { useDesk } from "@/lib/store";
import { cn } from "cn";

const COLORS = ["#22D3EE", "#10B981", "#F59E0B", "#94A3B8", "#EF4444", "#818CF8", "#F8FAFC", "#38BDF8"];

export default function PortfolioPage() {
  const snapshot = useDesk((state) => state.snapshot);
  const error = useDesk((state) => state.error);
  if (!snapshot && !error) return <LoadingBlock label="Loading the book." />;
  if (!snapshot) return <Empty title="Portfolio unavailable" body={error ?? "No portfolio model has been published."} />;
  const book = snapshot.portfolio;
  const allocation = [
    { name: "Cash", value: Math.max(book.available_cash, 0) },
    ...book.holdings.map((row) => ({ name: `${row.ticker} ${row.side}`, value: Math.abs(row.market_value) })),
  ].filter((row) => row.value > 0);
  const costs = [
    { name: "Brokerage", value: book.costs.brokerage },
    { name: "Taxes and fees", value: book.costs.taxes_and_fees },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
        <p className="text-sm text-[#94A3B8]">Figures come from the engine book. Valuation is marked {book.valuation}. Reliable: {book.reliable ? "yes" : "no"}.</p>
      </div>
      <Panel title="Holdings">
        {book.holdings.length === 0 ? (
          <Empty title="No open positions" body="Longs and shorts appear here after a confirmed fill. Rejected orders are not positions." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead>Side</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Avg</TableHead>
                <TableHead>Last</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Unrealized</TableHead>
                <TableHead>Exposure</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {book.holdings.map((row) => (
                <TableRow key={`${row.ticker}-${row.side}`}>
                  <TableCell>{row.ticker}</TableCell>
                  <TableCell className="uppercase">{row.side}</TableCell>
                  <TableCell className="num">{row.quantity}</TableCell>
                  <TableCell className="num">{inr(row.avg_price)}</TableCell>
                  <TableCell className="num">{inr(row.last)}</TableCell>
                  <TableCell className="num">{inr(row.market_value)}</TableCell>
                  <TableCell className={cn("num", pnlClass(row.unrealized_pnl))}>{inr(row.unrealized_pnl)} ({pct(row.unrealized_pnl_pct)})</TableCell>
                  <TableCell className="num">{pct(row.exposure_pct, 1)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Allocation">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={allocation} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} stroke="#0B1220">
                  {allocation.map((row, index) => (
                    <Cell key={row.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Equity history" className="xl:col-span-2">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={book.equity_history}>
                <CartesianGrid stroke="#1E293B" vertical={false} />
                <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} width={72} />
                <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                <Area dataKey="equity" stroke="#22D3EE" fill="#22D3EE22" name="Equity" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Cash utilization">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={book.equity_history}>
                <CartesianGrid stroke="#1E293B" vertical={false} />
                <XAxis dataKey="sim_day" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} width={72} />
                <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #334155" }} formatter={(value) => inr(Number(value))} />
                <Area dataKey="cash" stroke="#94A3B8" fill="#94A3B822" name="Cash" />
                <Area dataKey="invested" stroke="#F59E0B" fill="#F59E0B22" name="Invested" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Transaction costs">
          <p className="mb-3 text-xs text-[#94A3B8]">Model {book.costs.model}. Official schedule: {book.costs.official ? "yes" : "no"}.</p>
          <ul className="space-y-2">
            {costs.map((row) => (
              <li key={row.name} className="flex items-center justify-between rounded-lg bg-[#0B1220] px-3 py-2 text-sm">
                <span>{row.name}</span>
                <span className="num">{inr(row.value)}</span>
              </li>
            ))}
            <li className="flex items-center justify-between px-3 text-sm">
              <span>Realized gross</span>
              <span className={cn("num", pnlClass(book.realized_gross))}>{inr(book.realized_gross)}</span>
            </li>
            <li className="flex items-center justify-between px-3 text-sm">
              <span>Net P&L</span>
              <span className={cn("num", pnlClass(book.net_pnl))}>{inr(book.net_pnl)}</span>
            </li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}
