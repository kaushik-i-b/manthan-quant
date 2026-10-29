"use client";

import { useEffect } from "react";

import { apiUrl, wsUrl } from "@/lib/engine";
import { reconnectDelay } from "@/lib/format";
import { useDesk } from "@/lib/store";
import type { Candle, Snapshot } from "@/lib/types";

export function useDeskConnection() {
  const applySnapshot = useDesk((state) => state.applySnapshot);
  const applyEvent = useDesk((state) => state.applyEvent);
  const setStatus = useDesk((state) => state.setStatus);
  const setError = useDesk((state) => state.setError);
  const setCandles = useDesk((state) => state.setCandles);
  const markStale = useDesk((state) => state.markStale);

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function hydrate() {
      try {
        const response = await fetch(apiUrl("/api/snapshot"), { cache: "no-store" });
        if (!response.ok) throw new Error(`Engine responded ${response.status}`);
        const snapshot = (await response.json()) as Snapshot;
        if (stopped) return;
        applySnapshot(snapshot);
        await Promise.all(
          snapshot.tickers.map(async (row) => {
            const candleResponse = await fetch(apiUrl(`/api/candles/${row.ticker}`), { cache: "no-store" });
            if (!candleResponse.ok) return;
            const body = (await candleResponse.json()) as { candles: Candle[] };
            setCandles(row.ticker, body.candles);
          }),
        );
      } catch (error) {
        if (!stopped) setError(error instanceof Error ? error.message : "Engine unavailable");
      }
    }

    function connect() {
      if (stopped) return;
      setStatus("connecting");
      socket = new WebSocket(wsUrl());
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (message) => {
        try {
          applyEvent(JSON.parse(message.data));
        } catch {
          setError("Engine sent a message the desk could not read");
        }
      };
      socket.onerror = () => {
        setStatus("disconnected");
      };
      socket.onclose = () => {
        if (stopped) return;
        setStatus("disconnected");
        const delay = reconnectDelay(attempt);
        attempt += 1;
        timer = setTimeout(connect, delay);
      };
    }

    void hydrate();
    connect();
    const poll = setInterval(() => {
      void hydrate();
    }, 5000);
    const stale = setInterval(() => {
      const last = useDesk.getState().lastMessageAt;
      if (last > 0 && Date.now() - last > 8000) markStale();
    }, 2000);

    return () => {
      stopped = true;
      clearInterval(poll);
      clearInterval(stale);
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [applyEvent, applySnapshot, markStale, setCandles, setError, setStatus]);
}
