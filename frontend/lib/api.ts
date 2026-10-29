export const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

export const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
export const fmt2 = (n: number) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
export const pct = (n: number) => `${n >= 0 ? "+" : ""}${Number(n || 0).toFixed(2)}%`;
