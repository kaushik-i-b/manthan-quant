"use client";

import { create } from "zustand";

import { applyCandle, mergeCandles } from "@/lib/candles";
import type { Candle, Decision, EngineEvent, OrderRow, Snapshot } from "@/lib/types";

type Status = "idle" | "connecting" | "live" | "stale" | "disconnected" | "error";

type DeskState = {
  snapshot: Snapshot | null;
  candles: Record<string, Candle[]>;
  selected: string | null;
  status: Status;
  error: string | null;
  lastMessageAt: number;
  attempt: number;
  setStatus: (status: Status) => void;
  setError: (error: string | null) => void;
  setSelected: (ticker: string) => void;
  setCandles: (ticker: string, rows: Candle[]) => void;
  applySnapshot: (snapshot: Snapshot) => void;
  applyEvent: (event: EngineEvent) => void;
  markStale: () => void;
};

function withMilestone(snapshot: Snapshot, key: string): Snapshot {
  if (snapshot.milestones[key]) return snapshot;
  return { ...snapshot, milestones: { ...snapshot.milestones, [key]: true } };
}

export const useDesk = create<DeskState>((set) => ({
  snapshot: null,
  candles: {},
  selected: null,
  status: "idle",
  error: null,
  lastMessageAt: 0,
  attempt: 0,
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error, status: error ? "error" : "idle" }),
  setSelected: (ticker) => set({ selected: ticker }),
  setCandles: (ticker, rows) =>
    set((state) => ({
      candles: { ...state.candles, [ticker]: mergeCandles(state.candles[ticker] ?? [], rows) },
    })),
  applySnapshot: (snapshot) =>
    set((state) => ({
      snapshot,
      selected: state.selected ?? snapshot.tickers[0]?.ticker ?? null,
      status: "live",
      error: null,
      lastMessageAt: Date.now(),
      attempt: 0,
    })),
  markStale: () => set((state) => (state.status === "live" ? { status: "stale" } : {})),
  applyEvent: (event) =>
    set((state) => {
      const now = Date.now();
      if (event.type === "snapshot") {
        const snapshot = event.data as Snapshot;
        return {
          snapshot,
          selected: state.selected ?? snapshot.tickers[0]?.ticker ?? null,
          status: "live" as Status,
          error: null,
          lastMessageAt: now,
          attempt: 0,
        };
      }
      if (!state.snapshot) return { lastMessageAt: now, status: "live" };
      let snapshot = state.snapshot;
      let candles = state.candles;
      if (event.type === "market.tick") {
        const tick = event.data as Candle;
        candles = { ...candles, [tick.ticker]: applyCandle(candles[tick.ticker] ?? [], tick) };
        snapshot = withMilestone(
          {
            ...snapshot,
            health: { ...snapshot.health, sim_day: tick.sim_day, stale: false, feed: snapshot.health.feed },
            tickers: snapshot.tickers.map((row) =>
              row.ticker === tick.ticker
                ? {
                    ...row,
                    last: tick.close,
                    change: Number((tick.close - row.last).toFixed(2)),
                    change_pct: row.last ? Number((((tick.close - row.last) / row.last) * 100).toFixed(2)) : row.change_pct,
                    volume: tick.volume,
                    sim_day: tick.sim_day,
                  }
                : row,
            ),
          },
          "market_data",
        );
        if (tick.ema50 != null) snapshot = withMilestone(snapshot, "indicators");
      } else if (event.type === "market.news") {
        const item = event.data as Snapshot["news"][number];
        snapshot = { ...snapshot, news: [item, ...snapshot.news].slice(0, 30) };
      } else if (event.type === "strategy.signal") {
        const decision = event.data as Decision;
        snapshot = {
          ...snapshot,
          decisions: [decision, ...snapshot.decisions.filter((row) => row.id !== decision.id)].slice(0, 80),
        };
        if (decision.action !== "HOLD") snapshot = withMilestone(snapshot, "signal");
      } else if (event.type === "order.result") {
        const order = event.data as OrderRow;
        snapshot = {
          ...snapshot,
          orders: [order, ...snapshot.orders.filter((row) => row.client_order_id !== order.client_order_id)].slice(0, 80),
        };
        if (order.status === "FILLED") {
          snapshot = withMilestone(withMilestone(snapshot, "risk_pass"), "fill");
        }
      } else if (event.type === "portfolio.updated") {
        const portfolio = event.data as Snapshot["portfolio"];
        snapshot = { ...snapshot, portfolio };
        if (portfolio.net_pnl !== 0) snapshot = withMilestone(snapshot, "pnl_updated");
      } else if (event.type === "risk.alert") {
        const decision = event.data as Decision;
        snapshot = withMilestone(
          {
            ...snapshot,
            risk: { ...snapshot.risk, recent_rejections: [decision, ...snapshot.risk.recent_rejections].slice(0, 12) },
            decisions: [decision, ...snapshot.decisions.filter((row) => row.id !== decision.id)].slice(0, 80),
          },
          "risk_reject",
        );
      } else if (event.type === "system.health") {
        const health = event.data as Snapshot["health"];
        const recovered = state.snapshot.health.feed === "interrupted" && health.feed !== "interrupted";
        snapshot = { ...snapshot, health, lifecycle: { ...snapshot.lifecycle, stage: health.stage, lamp: health.lamp, sim_day: health.sim_day } };
        if (recovered) snapshot = withMilestone(snapshot, "outage_recovered");
      } else if (event.type === "simulation.stage") {
        const lifecycle = event.data as Snapshot["lifecycle"];
        snapshot = { ...snapshot, lifecycle, health: { ...snapshot.health, stage: lifecycle.stage, lamp: lifecycle.lamp, sim_day: lifecycle.sim_day } };
      }
      return { snapshot, candles, status: "live", error: null, lastMessageAt: now };
    }),
}));
