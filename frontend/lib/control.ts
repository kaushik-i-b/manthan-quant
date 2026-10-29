import { NextResponse } from "next/server";

export async function forwardControl(path: string, body?: unknown) {
  const engine = process.env.ENGINE_URL || "http://127.0.0.1:8741";
  const token = process.env.CONTROL_TOKEN || "dev-control-token";
  try {
    const response = await fetch(`${engine}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json({ ok: false, ack: false, error: "engine unreachable" }, { status: 502 });
  }
}
