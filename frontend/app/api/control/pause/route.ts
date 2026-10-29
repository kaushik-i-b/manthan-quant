import { forwardControl } from "@/lib/control";

export async function POST() {
  return forwardControl("/api/control/pause");
}

export const dynamic = "force-dynamic";
