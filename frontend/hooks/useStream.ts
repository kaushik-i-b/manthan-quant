"use client";
import { useEffect, useRef, useState } from "react";
import type { StreamMsg } from "@/types";

const WS_URL = (process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000/ws/stream");

export function useStream(onMsg: (m: StreamMsg) => void) {
  const [connected, setConnected] = useState(false);
  const [stale, setStale] = useState(false);
  const cb = useRef(onMsg);
  cb.current = onMsg;
  const lastTs = useRef<number>(Date.now());

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 1000;
    let alive = true;
    const staleTimer = setInterval(() => {
      setStale(Date.now() - lastTs.current > 8000);
    }, 2000);
    function connect() {
      if (!alive) return;
      try { ws = new WebSocket(WS_URL); } catch { schedule(); return; }
      ws.onopen = () => { setConnected(true); retry = 1000; };
      ws.onmessage = (ev) => {
        lastTs.current = Date.now();
        try { cb.current(JSON.parse(ev.data)); } catch { /* ignore */ }
      };
      ws.onclose = () => { setConnected(false); schedule(); };
      ws.onerror = () => { try { ws?.close(); } catch { /* */ } };
    }
    function schedule() {
      if (!alive) return;
      setTimeout(connect, retry);
      retry = Math.min(retry * 1.5, 10000);
    }
    connect();
    return () => { alive = false; clearInterval(staleTimer); try { ws?.close(); } catch { /* */ } };
  }, []);
  return { connected, stale };
}
