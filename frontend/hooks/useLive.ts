"use client";
import { create } from "zustand";
import type { Health, OrderRow, PortfolioSnap, SignalItem, StockRow, StreamMsg } from "@/types";

interface LiveState {
  health: Health | null;
  portfolio: PortfolioSnap | null;
  stocks: StockRow[];
  signals: SignalItem[];
  orders: OrderRow[];
  ticks: number;
  ingest: (m: StreamMsg) => void;
  setHealth: (h: Health) => void;
  setPortfolio: (p: PortfolioSnap) => void;
  setStocks: (s: StockRow[]) => void;
  setSignals: (s: SignalItem[]) => void;
  setOrders: (o: OrderRow[]) => void;
}

export const useLive = create<LiveState>((set) => ({
  health: null, portfolio: null, stocks: [], signals: [], orders: [], ticks: 0,
  setHealth: (health) => set({ health }),
  setPortfolio: (p) => set({ portfolio: p }),
  setStocks: (stocks) => set({ stocks }),
  setSignals: (signals) => set({ signals }),
  setOrders: (orders) => set({ orders }),
  ingest: (m) =>
    set((s) => {
      const t = m.type;
      if (t === "portfolio.updated") return { portfolio: m.payload as unknown as PortfolioSnap, ticks: s.ticks + 1 };
      if (t === "system.health") return { health: { ...(s.health as Health), ...(m.payload as object) } as Health, ticks: s.ticks + 1 };
      if (t === "strategy.signal") return { signals: [m.payload as unknown as SignalItem, ...s.signals].slice(0, 120), ticks: s.ticks + 1 };
      if (t === "order.result") {
        const o = m.payload as unknown as OrderRow;
        return { orders: [{ ticker: o.ticker, action: String((m.payload as {action?: unknown}).action ?? o.action), quantity: (m.payload as {quantity?: number}).quantity, status: String((m.payload as {status?: unknown}).status ?? ""), fill_price: (m.payload as {fill_price?: number}).fill_price, reason: (m.payload as {reason?: string}).reason, sim_day: Number((m.payload as {sim_day?: number}).sim_day ?? 0) }, ...s.orders].slice(0, 200), ticks: s.ticks + 1 };
      }
      return { ticks: s.ticks + 1 };
    }),
}));
