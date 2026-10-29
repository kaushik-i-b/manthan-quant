export type Action = "BUY" | "SELL" | "SHORT" | "COVER" | "HOLD";

export type Candle = {
  ticker: string;
  sim_day: number;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema9: number | null;
  ema21: number | null;
  ema50: number | null;
  rsi14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  source: string;
};

export type TickerRow = {
  ticker: string;
  name: string;
  synthetic: boolean;
  last: number;
  change: number;
  change_pct: number;
  volume: number;
  signal: Action | string;
  signal_score: number;
  trend: string;
  regime: string;
  strategy: string | null;
  sim_day: number;
};

export type Decision = {
  id: string;
  ticker: string;
  action: Action | string;
  signal_score: number;
  score_type: string;
  strategy: string;
  selector: string;
  regime: string;
  indicators: Record<string, number | boolean | null>;
  contributions: Record<string, { score: number; weight: number; weighted: number; reasons: string[] }>;
  risk_approved: boolean | null;
  risk_reasons: string[];
  executed: boolean;
  rejection_reason: string | null;
  reason: string;
  timestamp: string;
  sim_day: number;
  news_label: string | null;
  news_headline: string | null;
};

export type OrderRow = {
  order_id: string;
  client_order_id: string;
  ticker: string;
  action: string;
  quantity: number;
  price: number;
  sim_day: number;
  status: string;
  message: string;
  strategy: string;
  venue: string;
  brokerage: number;
  taxes_and_fees: number;
  timestamp: string;
  signal_score: number;
};

export type Holding = {
  ticker: string;
  name: string;
  side: string;
  quantity: number;
  avg_price: number;
  last: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number | null;
  exposure_pct: number | null;
  opened_day: number;
  synthetic: boolean;
};

export type EquityPoint = {
  sim_day: number;
  equity: number;
  cash: number;
  invested: number;
  gross_exposure: number;
  pnl: number;
  drawdown: number;
};

export type Snapshot = {
  meta: {
    project: string;
    data_origin: string;
    disclaimer: string;
    cost_model: string;
    cost_model_official: boolean;
    dry_run: boolean;
    trading_enabled: boolean;
    live_submission_armed: boolean;
    time_origin_unix: number;
    seconds_per_sim_day: number;
    missing_official_docs: string[];
    initial_capital: number;
  };
  health: {
    kafka: string;
    kafka_lag: number | null;
    trading_api: string;
    heartbeat: string;
    heartbeat_acks: number;
    heartbeat_error: string;
    stage: string;
    sim_day: number;
    active_strategy: string;
    last_primary_strategy: string | null;
    mode: string;
    lamp: string;
    feed: string;
    data_origin: string;
    paused: boolean;
    decision_latency_ms_p50: number | null;
    decision_latency_ms_max: number | null;
    rate_limit: { used: number; limit: number; remaining: number; note: string };
    stale: boolean;
    last_event_age_sec: number | null;
    dropped_duplicates: number;
    dropped_reorder: number;
    gaps: number;
  };
  lifecycle: { stage: string; heartbeat: string; acks: number; error: string; sim_day: number; lamp: string };
  portfolio: {
    starting_capital: number;
    cash: number;
    available_cash: number;
    locked_collateral: number;
    buying_power: number;
    invested: number;
    gross_exposure: number;
    short_exposure: number;
    realized_gross: number;
    unrealized_pnl: number;
    fees: number;
    brokerage: number;
    taxes_and_fees: number;
    net_pnl: number;
    equity: number;
    total_return_pct: number;
    drawdown_pct: number;
    max_drawdown_pct: number;
    win_rate: number | null;
    closed_trades: number;
    wins: number;
    losses: number;
    fills: number;
    valuation: string;
    reliable: boolean;
    holdings: Holding[];
    equity_history: EquityPoint[];
    costs: { brokerage: number; taxes_and_fees: number; model: string; official: boolean };
  };
  tickers: TickerRow[];
  decisions: Decision[];
  orders: OrderRow[];
  risk: {
    health: string;
    drawdown_pct: number;
    max_allowed_drawdown_pct: number;
    max_observed_drawdown_pct: number;
    gross_exposure: number;
    exposure_pct: number;
    cash: number;
    available_cash: number;
    cash_reserve_pct: number;
    min_cash_reserve_pct: number;
    largest_position: { ticker: string; exposure_pct: number; side: string } | null;
    short_exposure: number;
    paused: boolean;
    limits: { max_position_pct: number; max_invested_pct: number; max_orders_per_day: number; orders_today: number };
    recent_rejections: Decision[];
  };
  audit: { ts: string; event_type: string; payload: Record<string, unknown> }[];
  milestones: Record<string, boolean>;
  news: {
    event_id: string;
    ticker: string;
    sim_day: number;
    headline: string;
    body: string;
    sentiment: number | null;
    severity: number | null;
    label: string | null;
    source: string;
  }[];
};

export type EngineEvent = {
  type: string;
  data: unknown;
};

export type BacktestRow = {
  strategy: string;
  entry_threshold: number;
  total_return_pct: number;
  net_profit: number;
  ending_equity: number;
  max_drawdown_pct: number;
  sharpe: number | null;
  sharpe_note: string;
  win_rate: number | null;
  profit_factor: number | null;
  trade_count: number;
  closed_trades: number;
  turnover: number;
  transaction_costs: number;
  avg_cash: number;
  avg_exposure: number;
  rejected_orders: number;
  decision_latency_ms_p50: number | null;
  equity?: { sim_day: number; equity: number; drawdown: number }[];
  synthetic: boolean;
};

export type BacktestReport = {
  dataset: string;
  synthetic: boolean;
  disclaimer: string;
  seed: number;
  elapsed_ms: number;
  splits: { train: number[]; validation: number[]; test: number[] };
  selection_rule: string;
  selected_entry_threshold: number;
  train: BacktestRow[];
  validation: BacktestRow;
  test: BacktestRow;
  ranking: BacktestRow[];
  results: Record<string, BacktestRow>;
};
