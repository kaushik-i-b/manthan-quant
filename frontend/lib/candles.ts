import type { Candle } from "@/lib/types";

export function applyCandle(existing: Candle[], next: Candle): Candle[] {
  if (existing.length === 0) return [next];
  const last = existing[existing.length - 1];
  if (next.time === last.time && next.ticker === last.ticker) {
    return [...existing.slice(0, -1), next];
  }
  if (next.time > last.time && next.ticker === last.ticker) {
    return [...existing, next];
  }
  if (next.ticker !== last.ticker) return existing;
  return existing;
}

export function mergeCandles(base: Candle[], incoming: Candle[]): Candle[] {
  const map = new Map<number, Candle>();
  for (const row of base) map.set(row.time, row);
  for (const row of incoming) map.set(row.time, row);
  return [...map.values()].sort((a, b) => a.time - b.time);
}
