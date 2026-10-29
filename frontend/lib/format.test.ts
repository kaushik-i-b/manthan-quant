import { describe, expect, it } from "vitest";

import { applyCandle, mergeCandles } from "@/lib/candles";
import { inr, pct, reconnectDelay } from "@/lib/format";
import type { Candle } from "@/lib/types";

function candle(partial: Partial<Candle>): Candle {
  return {
    ticker: "RELIANCE",
    sim_day: 1,
    time: 100,
    open: 1,
    high: 2,
    low: 1,
    close: 2,
    volume: 10,
    ema9: null,
    ema21: null,
    ema50: null,
    rsi14: null,
    macd: null,
    macd_signal: null,
    macd_hist: null,
    source: "synthetic",
    ...partial,
  };
}

describe("formatters", () => {
  it("renders rupees and blanks", () => {
    expect(inr(1000)).toContain("1,000");
    expect(inr(null)).toBe("—");
    expect(pct(1.5)).toBe("+1.50%");
    expect(pct(-2)).toBe("-2.00%");
    expect(pct(null)).toBe("—");
  });

  it("backs off websocket reconnects", () => {
    expect(reconnectDelay(0)).toBe(500);
    expect(reconnectDelay(1)).toBe(1000);
    expect(reconnectDelay(8)).toBe(8000);
  });
});

describe("candles", () => {
  it("updates the last bar instead of appending a duplicate", () => {
    const first = candle({ close: 2 });
    const revised = candle({ close: 3 });
    const next = applyCandle([first], revised);
    expect(next).toHaveLength(1);
    expect(next[0].close).toBe(3);
  });

  it("appends a later bar and ignores a different ticker", () => {
    const rows = applyCandle([candle({ time: 100 })], candle({ time: 200, sim_day: 2 }));
    expect(rows.map((row) => row.time)).toEqual([100, 200]);
    const ignored = applyCandle(rows, candle({ ticker: "TCS", time: 300 }));
    expect(ignored).toHaveLength(2);
  });

  it("merges history without dropping a newer tick", () => {
    const merged = mergeCandles(
      [candle({ time: 100 }), candle({ time: 200, close: 9 })],
      [candle({ time: 100, close: 1 }), candle({ time: 150, close: 4 })],
    );
    expect(merged.map((row) => row.time)).toEqual([100, 150, 200]);
    expect(merged.find((row) => row.time === 200)?.close).toBe(9);
  });
});
