export interface Health {
  stage: string; sim_day: number; kafka: string; api_ok: boolean;
  heartbeat_ok: boolean; dry_run: boolean; trading_enabled: boolean;
  decisions: number; avg_decision_ms: number; api_latency_ms: number;
  rate_used: number; rate_limit: number; uptime_s: number;
}
export interface Position { ticker: string; qty: number; avg_price: number; short_qty: number; short_avg: number; }
export interface PortfolioSnap {
  cash: number; equity: number; invested: number; realized_pnl: number;
  unrealized_pnl: number; total_return_pct: number; drawdown_pct: number;
  positions: Record<string, Position>; sim_day: number;
}
export interface StockRow { ticker: string; price: number; indicators: Record<string, number | null>; news?: NewsItem | null; }
export interface NewsItem { ticker: string; headline: string; sentiment: string; severity: number; sim_day: number; }
export interface SignalItem {
  ticker: string; action: string; score: number; strategy: string;
  indicators: Record<string, unknown>; reason: string; regime?: string;
  sentiment?: string; risk_passed?: boolean; risk_reason?: string; sim_day: number;
}
export interface OrderRow { ticker: string; action: string; quantity?: number; status: string; fill_price?: number; reason?: string; sim_day: number; }
export interface StreamMsg { type: string; payload: Record<string, unknown>; server_ts: number }
