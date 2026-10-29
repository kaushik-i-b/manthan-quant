"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import type { Candle } from "@/lib/types";

type Props = {
  candles: Candle[];
  ticker: string;
  origin: number;
};

export function CandleChart({ candles, ticker, origin }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeries = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeries = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema9 = useRef<ISeriesApi<"Line"> | null>(null);
  const ema21 = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50 = useRef<ISeriesApi<"Line"> | null>(null);
  const signature = useRef("");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const chart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "#151F30" }, textColor: "#94A3B8", fontFamily: "var(--font-geist-mono), monospace" },
      grid: { vertLines: { color: "#1E293B" }, horzLines: { color: "#1E293B" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#334155" },
      timeScale: {
        borderColor: "#334155",
        tickMarkFormatter: (time: number) => `D${Math.round((Number(time) - origin) / 86400)}`,
      },
      localization: {
        timeFormatter: (time: number) => `Day ${Math.round((Number(time) - origin) / 86400)}`,
      },
      autoSize: true,
    });
    candleSeries.current = chart.addSeries(CandlestickSeries, {
      upColor: "#10B981",
      downColor: "#EF4444",
      borderVisible: false,
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });
    volumeSeries.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
    ema9.current = chart.addSeries(LineSeries, { color: "#22D3EE", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    ema21.current = chart.addSeries(LineSeries, { color: "#F59E0B", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    ema50.current = chart.addSeries(LineSeries, { color: "#A78BFA", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    chartRef.current = chart;
    return () => {
      chart.remove();
      chartRef.current = null;
      signature.current = "";
    };
  }, [origin]);

  useEffect(() => {
    if (!candleSeries.current || candles.length === 0) return;
    const last = candles[candles.length - 1];
    const key = `${ticker}:${candles.length}:${last.time}:${last.close}`;
    const incremental = signature.current.startsWith(`${ticker}:`) && signature.current.split(":")[1] === String(candles.length - 1);
    const bar = {
      time: last.time as UTCTimestamp,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
    };
    if (incremental) {
      candleSeries.current.update(bar);
      volumeSeries.current?.update({
        time: last.time as UTCTimestamp,
        value: last.volume,
        color: last.close >= last.open ? "rgba(16,185,129,0.45)" : "rgba(239,68,68,0.45)",
      });
      if (last.ema9 != null) ema9.current?.update({ time: last.time as UTCTimestamp, value: last.ema9 });
      if (last.ema21 != null) ema21.current?.update({ time: last.time as UTCTimestamp, value: last.ema21 });
      if (last.ema50 != null) ema50.current?.update({ time: last.time as UTCTimestamp, value: last.ema50 });
    } else {
      candleSeries.current.setData(candles.map((row) => ({ time: row.time as UTCTimestamp, open: row.open, high: row.high, low: row.low, close: row.close })));
      volumeSeries.current?.setData(
        candles.map((row) => ({
          time: row.time as UTCTimestamp,
          value: row.volume,
          color: row.close >= row.open ? "rgba(16,185,129,0.45)" : "rgba(239,68,68,0.45)",
        })),
      );
      const line = (pick: (row: Candle) => number | null) =>
        candles.filter((row) => pick(row) != null).map((row) => ({ time: row.time as UTCTimestamp, value: pick(row) as number }));
      ema9.current?.setData(line((row) => row.ema9));
      ema21.current?.setData(line((row) => row.ema21));
      ema50.current?.setData(line((row) => row.ema50));
      chartRef.current?.timeScale().fitContent();
    }
    signature.current = key;
  }, [candles, ticker]);

  return <div ref={host} className="h-[440px] w-full" />;
}
