"use client";
import { Providers } from "../providers";
import { Card, Empty } from "@/components/ui";
import { useLive } from "@/hooks/useLive";
import { fmtINR, fmt2, pct } from "@/lib/api";

function PfInner() {
  const { portfolio, stocks } = useLive();
  if (!portfolio) return <Empty msg="Loading portfolio…" />;
  const px: Record<string, number> = {};
  stocks.forEach((s) => (px[s.ticker] = s.price));
  const rows = Object.values(portfolio.positions).filter((p) => p.qty !== 0 || p.short_qty !== 0);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Equity", fmtINR(portfolio.equity)], ["Cash", fmtINR(portfolio.cash)], ["Realized P&L", fmtINR(portfolio.realized_pnl)], ["Unrealized P&L", fmtINR(portfolio.unrealized_pnl)]].map(([k, v]) => (
          <div key={k} className="bg-panel border border-bord rounded-xl p-4"><div className="text-[11px] uppercase tracking-wider text-muted">{k}</div><div className="text-xl font-bold num mt-1">{v}</div></div>))}
      </div>
      <Card title="Holdings" sub="From backend portfolio model — estimated vs confirmed reconciled server-side">
        {rows.length === 0 ? <Empty msg="No open positions. Engine holds cash until signals clear risk." /> : (
          <div className="overflow-auto"><table className="w-full text-xs num">
            <thead><tr className="text-muted text-left"><th>Ticker</th><th>Qty</th><th>Avg</th><th>LTP</th><th>Value</th><th>Unreal</th><th>Type</th></tr></thead>
            <tbody>{rows.map((r) => {
              const ltp = px[r.ticker] ?? r.avg_price;
              const un = (ltp - r.avg_price) * r.qty;
              return <tr key={r.ticker} className="border-t border-bord">
                <td className="py-2 font-bold">{r.ticker}</td><td>{r.qty}{r.short_qty ? ` (${r.short_qty}S)` : ""}</td>
                <td>₹{fmt2(r.avg_price)}</td><td>₹{fmt2(ltp)}</td><td>{fmtINR(r.qty * ltp)}</td>
                <td className={un >= 0 ? "text-profit" : "text-loss"}>{fmtINR(un)}</td>
                <td>{r.short_qty ? "SHORT" : "LONG"}</td></tr>;
            })}</tbody>
          </table></div>)}
      </Card>
      <Card title="Cash utilization" sub={`Invested ${pct((portfolio.invested / Math.max(portfolio.equity, 1)) * 100)} of equity`}>
        <div className="h-3 rounded-full bg-surface overflow-hidden">
          <div className="h-full bg-accent" style={{ width: `${Math.min(100, (portfolio.invested / Math.max(portfolio.equity, 1)) * 100)}%` }} />
        </div>
      </Card>
    </div>
  );
}
export default function Page() { return <Providers><PfInner /></Providers>; }
