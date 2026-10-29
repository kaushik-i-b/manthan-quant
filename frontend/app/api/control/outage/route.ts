import { forwardControl } from "@/lib/control";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({ seconds: 6 }));
  return forwardControl("/api/demo/outage", body);
}

export const dynamic = "force-dynamic";
